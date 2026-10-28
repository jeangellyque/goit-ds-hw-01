from __future__ import annotations

from abc import ABC, abstractmethod
import pickle
from collections import UserDict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Callable


WELCOME_MESSAGE = "Welcome to the assistant bot!"
GOODBYE_MESSAGE = "Good bye!"
HELLO_MESSAGE = "How can I help you?"
INVALID_COMMAND_MESSAGE = "Invalid command."
CONTACT_NOT_FOUND_MESSAGE = "Contact not found."
NO_CONTACTS_MESSAGE = "No contacts saved."
ADDRESS_BOOK_FILE = Path(__file__).with_name("addressbook.pkl")
INPUT_PROMPT = "Enter a command: "


class Field:
    def __init__(self, value: str):
        self.value = value

    @property
    def value(self) -> str:
        return self._value

    @value.setter
    def value(self, new_value: str) -> None:
        self._value = self.validate(new_value)

    def validate(self, value: str) -> str:
        return str(value)

    def __str__(self) -> str:
        return self.value


class Name(Field):
    def validate(self, value: str) -> str:
        normalized_value = str(value).strip()
        if not normalized_value:
            raise ValueError("Name cannot be empty.")
        return normalized_value


class Phone(Field):
    def validate(self, value: str) -> str:
        normalized_value = str(value).strip()
        if len(normalized_value) != 10 or not normalized_value.isdigit():
            raise ValueError("Phone number must contain exactly 10 digits.")
        return normalized_value


class Birthday(Field):
    def validate(self, value: str) -> str:
        normalized_value = str(value).strip()
        try:
            parsed_date = datetime.strptime(normalized_value, "%d.%m.%Y")
        except ValueError as error:
            raise ValueError("Invalid date format. Use DD.MM.YYYY") from error
        return parsed_date.strftime("%d.%m.%Y")

    def as_date(self) -> date:
        return datetime.strptime(self.value, "%d.%m.%Y").date()


class Record:
    def __init__(self, name: str):
        self.name = Name(name)
        self.phones: list[Phone] = []
        self.birthday: Birthday | None = None

    def add_phone(self, phone: str) -> None:
        self.phones.append(Phone(phone))

    def remove_phone(self, phone: str) -> None:
        phone_to_remove = self.find_phone(phone)
        if phone_to_remove is None:
            raise ValueError(f"Phone {phone} not found.")
        self.phones.remove(phone_to_remove)

    def edit_phone(self, old_phone: str, new_phone: str) -> None:
        phone_to_edit = self.find_phone(old_phone)
        if phone_to_edit is None:
            raise ValueError(f"Phone {old_phone} not found.")
        phone_to_edit.value = new_phone

    def find_phone(self, phone: str) -> Phone | None:
        for saved_phone in self.phones:
            if saved_phone.value == phone:
                return saved_phone
        return None

    def add_birthday(self, birthday: str) -> None:
        self.birthday = Birthday(birthday)

    def __str__(self) -> str:
        phones_text = "; ".join(phone.value for phone in self.phones) or "no phones"
        birthday_text = self.birthday.value if self.birthday is not None else "not set"
        return (
            f"Contact name: {self.name.value}, "
            f"phones: {phones_text}, "
            f"birthday: {birthday_text}"
        )


@dataclass(frozen=True)
class CommandInfo:
    syntax: str
    description: str


COMMANDS: tuple[CommandInfo, ...] = (
    CommandInfo("hello", "Show a greeting."),
    CommandInfo("add <name> <phone>", "Add a contact or append a phone number."),
    CommandInfo("change <name> <old_phone> <new_phone>", "Change an existing phone number."),
    CommandInfo("phone <name>", "Show all phone numbers for a contact."),
    CommandInfo("all", "Show all saved contacts as cards."),
    CommandInfo("add-birthday <name> <DD.MM.YYYY>", "Save a birthday for a contact."),
    CommandInfo("show-birthday <name>", "Show a saved birthday."),
    CommandInfo("birthdays", "Show birthdays within the next 7 days."),
    CommandInfo("help", "Show the list of available commands."),
    CommandInfo("close / exit", "Save data and close the assistant."),
)


class AddressBook(UserDict):
    def add_record(self, record: Record) -> None:
        self.data[record.name.value] = record

    def find(self, name: str) -> Record | None:
        return self.data.get(name)

    def delete(self, name: str) -> None:
        self.data.pop(name, None)

    def get_records(self) -> list[Record]:
        return [self.data[name] for name in sorted(self.data)]

    def get_upcoming_birthdays(self) -> list[dict[str, str]]:
        today = date.today()
        upcoming_birthdays: list[dict[str, str]] = []

        for record in self.data.values():
            if record.birthday is None:
                continue

            birthday_date = record.birthday.as_date()
            next_birthday = self._get_next_birthday_date(birthday_date, today)
            days_until_birthday = (next_birthday - today).days

            if 0 <= days_until_birthday <= 7:
                congratulation_date = self._shift_from_weekend(next_birthday)
                upcoming_birthdays.append(
                    {
                        "name": record.name.value,
                        "birthday": congratulation_date.strftime("%d.%m.%Y"),
                    }
                )

        return sorted(
            upcoming_birthdays,
            key=lambda item: datetime.strptime(item["birthday"], "%d.%m.%Y"),
        )

    @staticmethod
    def _get_next_birthday_date(birthday_date: date, today: date) -> date:
        year = today.year

        while True:
            try:
                next_birthday = date(year, birthday_date.month, birthday_date.day)
            except ValueError:
                year += 1
                continue

            if next_birthday < today:
                year += 1
                continue

            return next_birthday

    @staticmethod
    def _shift_from_weekend(target_date: date) -> date:
        if target_date.weekday() == 5:
            return target_date + timedelta(days=2)
        if target_date.weekday() == 6:
            return target_date + timedelta(days=1)
        return target_date

    def __str__(self) -> str:
        if not self.data:
            return NO_CONTACTS_MESSAGE
        return "\n".join(str(record) for record in self.get_records())


class UserView(ABC):
    @property
    @abstractmethod
    def input_prompt(self) -> str:
        """Return the prompt shown before reading the next command."""

    @abstractmethod
    def render_message(self, message: str) -> str:
        """Render a plain text message."""

    @abstractmethod
    def render_contact(self, record: Record) -> str:
        """Render a single contact card."""

    @abstractmethod
    def render_contacts(self, records: list[Record]) -> str:
        """Render a collection of contact cards."""

    @abstractmethod
    def render_birthdays(self, upcoming_birthdays: list[dict[str, str]]) -> str:
        """Render the birthdays page."""

    @abstractmethod
    def render_commands(self, commands: tuple[CommandInfo, ...]) -> str:
        """Render the available commands page."""


class ConsoleView(UserView):
    @property
    def input_prompt(self) -> str:
        return INPUT_PROMPT

    def render_message(self, message: str) -> str:
        return message

    def render_contact(self, record: Record) -> str:
        phones_text = "; ".join(phone.value for phone in record.phones) or "no phones"
        birthday_text = self._format_birthday(record)
        return self._render_box(
            f"Name: {record.name.value}",
            f"Phones: {phones_text}",
            f"Birthday: {birthday_text}",
        )

    def render_contacts(self, records: list[Record]) -> str:
        if not records:
            return NO_CONTACTS_MESSAGE
        return "\n\n".join(self.render_contact(record) for record in records)

    def render_birthdays(self, upcoming_birthdays: list[dict[str, str]]) -> str:
        if not upcoming_birthdays:
            return "No upcoming birthdays."

        return "\n".join(
            f"{item['name']}: {item['birthday']}" for item in upcoming_birthdays
        )

    def render_commands(self, commands: tuple[CommandInfo, ...]) -> str:
        width = max(len(command.syntax) for command in commands)
        lines = ["Available commands:"]
        lines.extend(
            f"{command.syntax.ljust(width)} - {command.description}"
            for command in commands
        )
        return "\n".join(lines)

    @staticmethod
    def _format_birthday(record: Record) -> str:
        if record.birthday is None:
            return "not set"
        return record.birthday.value

    @staticmethod
    def _render_box(*lines: str) -> str:
        width = max(len(line) for line in lines)
        border = f"+-{'-' * width}-+"
        content = [f"| {line.ljust(width)} |" for line in lines]
        return "\n".join([border, *content, border])


def save_data(book: AddressBook, filename: Path = ADDRESS_BOOK_FILE) -> None:
    with open(filename, "wb") as file:
        pickle.dump(book, file)


def load_data(filename: Path = ADDRESS_BOOK_FILE) -> AddressBook:
    if not filename.exists():
        return AddressBook()

    with open(filename, "rb") as file:
        return pickle.load(file)


def input_error(func: Callable) -> Callable:
    @wraps(func)
    def inner(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KeyError:
            return CONTACT_NOT_FOUND_MESSAGE
        except ValueError as error:
            return str(error)

    return inner


def parse_input(user_input: str) -> tuple[str, list[str]]:
    parts = user_input.strip().split()
    if not parts:
        return "", []

    command, *args = parts
    return command.lower(), args


def require_args(args: list[str], count: int, message: str) -> None:
    if len(args) < count:
        raise ValueError(message)


@input_error
def add_contact(args: list[str], book: AddressBook) -> str:
    require_args(args, 2, "Give me name and phone please.")

    name, phone = args[0], args[1]
    record = book.find(name)
    message = "Contact updated."

    if record is None:
        record = Record(name)
        book.add_record(record)
        message = "Contact added."

    record.add_phone(phone)
    return message


@input_error
def change_contact(args: list[str], book: AddressBook) -> str:
    require_args(args, 3, "Give me name, old phone and new phone please.")

    name, old_phone, new_phone = args[0], args[1], args[2]
    record = book.find(name)
    if record is None:
        raise KeyError

    record.edit_phone(old_phone, new_phone)
    return "Contact updated."


@input_error
def show_phone(args: list[str], book: AddressBook) -> str:
    require_args(args, 1, "Enter user name.")

    record = book.find(args[0])
    if record is None:
        raise KeyError
    if not record.phones:
        return "No phones found for this contact."

    return "; ".join(phone.value for phone in record.phones)


@input_error
def show_all(args: list[str], book: AddressBook) -> list[Record]:
    if args:
        raise ValueError("The 'all' command does not take arguments.")
    return book.get_records()


@input_error
def add_birthday(args: list[str], book: AddressBook) -> str:
    require_args(args, 2, "Give me name and birthday please.")

    name, birthday = args[0], args[1]
    record = book.find(name)
    if record is None:
        raise KeyError

    record.add_birthday(birthday)
    return "Birthday added."


@input_error
def show_birthday(args: list[str], book: AddressBook) -> str:
    require_args(args, 1, "Enter user name.")

    record = book.find(args[0])
    if record is None:
        raise KeyError
    if record.birthday is None:
        return "Birthday is not set."

    return record.birthday.value


@input_error
def birthdays(args: list[str], book: AddressBook) -> list[dict[str, str]]:
    if args:
        raise ValueError("The 'birthdays' command does not take arguments.")

    return book.get_upcoming_birthdays()


@input_error
def show_help(args: list[str]) -> tuple[CommandInfo, ...]:
    if args:
        raise ValueError("The 'help' command does not take arguments.")
    return COMMANDS


@input_error
def say_hello(args: list[str]) -> str:
    if args:
        raise ValueError("The 'hello' command does not take arguments.")
    return HELLO_MESSAGE


@input_error
def say_goodbye(args: list[str]) -> str:
    if args:
        raise ValueError("The 'close' and 'exit' commands do not take arguments.")
    return GOODBYE_MESSAGE


def process_command(
    command: str, args: list[str], book: AddressBook, view: UserView
) -> tuple[str, bool]:
    if command in {"close", "exit"}:
        response = say_goodbye(args)
        return view.render_message(response), response == GOODBYE_MESSAGE
    if command == "hello":
        return view.render_message(say_hello(args)), False
    if command == "add":
        return view.render_message(add_contact(args, book)), False
    if command == "change":
        return view.render_message(change_contact(args, book)), False
    if command == "phone":
        return view.render_message(show_phone(args, book)), False
    if command == "all":
        response = show_all(args, book)
        if isinstance(response, str):
            return view.render_message(response), False
        return view.render_contacts(response), False
    if command == "add-birthday":
        return view.render_message(add_birthday(args, book)), False
    if command == "show-birthday":
        return view.render_message(show_birthday(args, book)), False
    if command == "birthdays":
        response = birthdays(args, book)
        if isinstance(response, str):
            return view.render_message(response), False
        return view.render_birthdays(response), False
    if command == "help":
        response = show_help(args)
        if isinstance(response, str):
            return view.render_message(response), False
        return view.render_commands(response), False
    return view.render_message(INVALID_COMMAND_MESSAGE), False


def main() -> None:
    book = load_data()
    view = ConsoleView()
    print(view.render_message(WELCOME_MESSAGE))

    try:
        while True:
            user_input = input(view.input_prompt)
            command, args = parse_input(user_input)
            response, should_exit = process_command(command, args, book, view)
            print(response)
            if should_exit:
                break
    finally:
        save_data(book)


if __name__ == "__main__":
    main()
