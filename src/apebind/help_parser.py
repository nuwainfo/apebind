#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import annotations

import re

from attrs import define

from .models import CommandSpec, OptionSpec, PositionalSpec, ValueType
from .naming import to_snake_case_identifier

@define(frozen=True)
class ParsedCommandSection:
    name: str
    positionals: tuple[PositionalSpec, ...]
    options: tuple[OptionSpec, ...]

@define(frozen=True)
class ParsedHelp:
    summary: str
    usage_path: tuple[str, ...]
    subcommands: tuple[str, ...]
    positionals: tuple[PositionalSpec, ...]
    options: tuple[OptionSpec, ...]
    command_sections: tuple[ParsedCommandSection, ...]

class HelpParser:
    """Parse common argparse, Click, clap, Cobra, and named command sections."""

    _SECTION_RE = re.compile(r'^([A-Za-z][A-Za-z0-9_. -]*):\s*$')
    _ENTRY_RE = re.compile(r'^\s{2,}([^\s].*?)(?:\s{2,}|\t+)(.+?)\s*$')
    _USAGE_RE = re.compile(r'^\s*usage:\s+(\S+)(?:\s+(.*))?$', re.IGNORECASE)
    _SUBCOMMAND_SECTIONS = ('commands', 'subcommands', 'available commands')
    _OPTION_SECTIONS = ('options', 'optional arguments', 'flags', 'global options')
    _POSITIONAL_SECTIONS = ('positional arguments', 'arguments')
    _GENERIC_USAGE_POSITIONALS = {'ARGS', 'ARGUMENTS', 'COMMAND', 'COMMANDS', 'OPTIONS'}

    @staticmethod
    def _is_command_name(value: str) -> bool:
        return bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', value))

    @staticmethod
    def _looks_like_metavar(value: str) -> bool:
        letters = ''.join(character for character in value if character.isalpha())

        return bool(letters) and letters.upper() == letters

    @staticmethod
    def _parse_choices(meta: str) -> tuple[str, ...]:
        choice_match = re.search(r'\{([^{}]+)\}', meta.strip())
        if not choice_match:
            return ()

        return tuple(part.strip() for part in choice_match.group(1).split(','))

    @staticmethod
    def _find_command_section(
        parsed_help: ParsedHelp,
        name: str,
    ) -> ParsedCommandSection | None:
        return next(
            (section for section in parsed_help.command_sections if section.name == name),
            None,
        )

    @classmethod
    def _usage_text(cls, lines: list[str]) -> str:
        usage_lines: list[str] = []
        collecting = False

        for line in lines:
            if not collecting:
                if cls._USAGE_RE.match(line):
                    collecting = True
                    usage_lines.append(line.strip())
                continue
            if not line.strip():
                break
            if line[:1].isspace():
                usage_lines.append(line.strip())
                continue
            break

        return ' '.join(usage_lines)

    @staticmethod
    def _strip_usage_launcher(tokens: list[str]) -> list[str]:
        if len(tokens) >= 2 and tokens[0] == '-m':
            return tokens[2:]

        return tokens

    @classmethod
    def _usage_tokens(cls, lines: list[str]) -> list[str]:
        usage_text = cls._usage_text(lines)
        match = cls._USAGE_RE.match(usage_text)
        if not match:
            return []

        remainder = match.group(2) or ''
        return cls._strip_usage_launcher(remainder.split())

    @classmethod
    def _usage_path(cls, lines: list[str]) -> tuple[str, ...]:
        command_path: list[str] = []

        for token in cls._usage_tokens(lines):
            candidate = token.rstrip(',')
            if candidate.startswith(('[', '{', '<', '-')):
                break
            if not cls._is_command_name(candidate):
                break
            if cls._looks_like_metavar(candidate):
                break

            command_path.append(candidate)

        return tuple(command_path)

    @classmethod
    def _find_summary(cls, lines: list[str]) -> str:
        collecting_usage = False
        usage_finished = False

        for line in lines:
            if not collecting_usage:
                if cls._USAGE_RE.match(line):
                    collecting_usage = True
                continue
            if not usage_finished:
                if not line.strip():
                    usage_finished = True
                continue

            stripped = line.strip()
            if not stripped:
                continue
            if cls._SECTION_RE.match(line):
                return ''
            return stripped

        return ''

    @classmethod
    def _collect_section_entries(cls, lines: list[str]) -> dict[str, list[tuple[str, str]]]:
        entries_by_section: dict[str, list[tuple[str, str]]] = {}
        section_name: str | None = None
        current_entry_index: int | None = None

        for line in lines:
            section_match = cls._SECTION_RE.match(line)
            if section_match:
                section_name = section_match.group(1).strip().lower()
                entries_by_section.setdefault(section_name, [])
                current_entry_index = None
                continue
            if section_name is None or not line.strip():
                current_entry_index = None
                continue

            entry_match = cls._ENTRY_RE.match(line)
            if entry_match:
                entries_by_section[section_name].append(
                    (entry_match.group(1).strip(), entry_match.group(2).strip())
                )
                current_entry_index = len(entries_by_section[section_name]) - 1
                continue

            indentation = len(line) - len(line.lstrip())
            stripped = line.strip()
            known_non_positional_sections = cls._OPTION_SECTIONS + cls._SUBCOMMAND_SECTIONS
            if indentation <= 4 and (
                stripped.startswith('-')
                or section_name in cls._POSITIONAL_SECTIONS
                or section_name not in known_non_positional_sections
            ):
                entries_by_section[section_name].append((stripped, ''))
                current_entry_index = len(entries_by_section[section_name]) - 1
                continue

            if current_entry_index is None or indentation <= 4:
                continue
            token, description = entries_by_section[section_name][current_entry_index]
            joined_description = f'{description} {stripped}'.strip()
            entries_by_section[section_name][current_entry_index] = (
                token,
                joined_description,
            )

        return entries_by_section

    @classmethod
    def _find_positional_choice_names(cls, lines: list[str]) -> set[str]:
        section_name: str | None = None
        choice_names: set[str] = set()

        for line in lines:
            section_match = cls._SECTION_RE.match(line)
            if section_match:
                section_name = section_match.group(1).strip().lower()
                continue
            if section_name not in cls._POSITIONAL_SECTIONS:
                continue
            choice_match = re.fullmatch(r'\{([^}]+)\}', line.strip())
            if choice_match:
                choice_names.update(part.strip() for part in choice_match.group(1).split(','))

        return choice_names

    @classmethod
    def _parse_subcommands(
        cls,
        lines: list[str],
        entries_by_section: dict[str, list[tuple[str, str]]],
    ) -> list[str]:
        subcommands: list[str] = []

        for section_name in cls._SUBCOMMAND_SECTIONS:
            for token, _description in entries_by_section.get(section_name, []):
                command_name = token.split()[0].strip(',')
                if cls._is_command_name(command_name):
                    subcommands.append(command_name)

        positional_entries: list[tuple[str, str]] = []

        for section_name in cls._POSITIONAL_SECTIONS:
            positional_entries.extend(entries_by_section.get(section_name, []))

        described_names = {
            token
            for token, _description in positional_entries
            if cls._is_command_name(token)
        }
        choice_names = cls._find_positional_choice_names(lines)

        for command_name in sorted(choice_names & described_names):
            subcommands.append(command_name)

        return list(dict.fromkeys(subcommands))

    @classmethod
    def _api_name_for_flags(cls, flags: tuple[str, ...]) -> str:
        preferred = next((flag for flag in flags if flag.startswith('--')), flags[0])

        return to_snake_case_identifier(preferred.lstrip('-'))

    @classmethod
    def _infer_value_type(cls, meta: str) -> ValueType:
        upper_meta = meta.upper()

        if any(
            word in upper_meta
            for word in ('COUNT', 'NUM', 'NUMBER', 'PORT', 'REPEAT', 'TIMEOUT', 'PERCENTAGE')
        ):
            return ValueType.INTEGER

        if any(word in upper_meta for word in ('PATH', 'FILE', 'DIR', 'DIRECTORY', 'FOLDER')):
            return ValueType.PATH

        return ValueType.STRING

    @staticmethod
    def _meta_is_multiple(meta: str) -> bool:
        return bool(re.search(r'\s\.\.\.(?:\]|$)', meta))

    @classmethod
    def _parse_option(cls, token: str, description: str) -> OptionSpec | None:
        aliases = re.split(r',\s*(?=-{1,2}[A-Za-z0-9])', token.strip())
        flags: list[str] = []
        metas: list[str] = []

        for alias in aliases:
            parts = alias.strip().split(maxsplit=1)
            if not parts or not parts[0].startswith('-'):
                continue
            flags.append(parts[0])
            if len(parts) > 1:
                metas.append(parts[1].strip())

        if not flags:
            return None

        meta = next((value for value in metas if value), '')
        flag_tuple = tuple(flags)

        return OptionSpec(
            flags=flag_tuple,
            api_name=cls._api_name_for_flags(flag_tuple),
            value_type=ValueType.BOOLEAN if not meta else cls._infer_value_type(meta),
            multiple=cls._meta_is_multiple(meta),
            value_optional=meta.startswith('[') and meta.endswith(']'),
            choices=cls._parse_choices(meta),
            help=description,
        )

    @classmethod
    def _parse_options_from_entries(
        cls,
        entries: list[tuple[str, str]],
    ) -> list[OptionSpec]:
        options: list[OptionSpec] = []

        for token, description in entries:
            parsed_option = cls._parse_option(token, description)
            if parsed_option is None:
                continue
            if '--help' in parsed_option.flags or '-h' in parsed_option.flags:
                continue
            options.append(parsed_option)

        return options

    @classmethod
    def _parse_options(
        cls,
        entries_by_section: dict[str, list[tuple[str, str]]],
    ) -> list[OptionSpec]:
        entries: list[tuple[str, str]] = []

        for section_name in cls._OPTION_SECTIONS:
            entries.extend(entries_by_section.get(section_name, []))

        return cls._parse_options_from_entries(entries)

    @classmethod
    def _parse_positionals_from_entries(
        cls,
        entries: list[tuple[str, str]],
        usage_text: str,
        subcommands: list[str],
    ) -> list[PositionalSpec]:
        positionals: list[PositionalSpec] = []
        subcommand_set = set(subcommands)

        for token, description in entries:
            name = token.split()[0]
            if name.startswith('{') or name in subcommand_set or name.startswith('-'):
                continue
            required_multiple = f'{name} [{name} ...]' in usage_text
            multiple = (
                required_multiple
                or f'{name} ...' in usage_text
                or f'[{name} ...]' in usage_text
            )
            optional = not required_multiple and f'[{name}' in usage_text
            positionals.append(
                PositionalSpec(
                    name=name,
                    api_name=to_snake_case_identifier(name),
                    value_type=cls._infer_value_type(name),
                    required=not optional,
                    multiple=multiple,
                    help=description,
                )
            )

        return positionals

    @classmethod
    def _parse_usage_positional(cls, token: str) -> PositionalSpec | None:
        value = token.strip().rstrip(',')
        optional = value.startswith('[')
        multiple = value.endswith('...')

        if multiple:
            value = value[:-3].rstrip()

        if optional:
            if not value.endswith(']'):
                return None

            value = value[1:-1].strip()

        if value.startswith('<') and value.endswith('>'):
            value = value[1:-1].strip()

        if value.endswith('...'):
            multiple = True
            value = value[:-3].rstrip()

        parts = value.split()
        if len(parts) == 2 and parts[1] == '...':
            multiple = True
            value = parts[0]
        elif len(parts) != 1:
            return None

        name = value.strip()
        if not name or name.startswith(('-', '{')):
            return None

        if name.upper() in cls._GENERIC_USAGE_POSITIONALS:
            return None

        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]*', name):
            return None

        return PositionalSpec(
            name=name,
            api_name=to_snake_case_identifier(name),
            value_type=cls._infer_value_type(name),
            required=not optional,
            multiple=multiple,
        )

    @classmethod
    def _parse_positionals_from_usage(
        cls,
        usage_text: str,
        usage_path: tuple[str, ...],
    ) -> list[PositionalSpec]:
        match = cls._USAGE_RE.match(usage_text)
        if not match:
            return []

        remainder = match.group(2) or ''
        tokens = cls._strip_usage_launcher(remainder.split())

        for command_name in usage_path:
            if not tokens or tokens[0].rstrip(',') != command_name:
                return []

            tokens.pop(0)

        syntax = ' '.join(tokens)
        usage_tokens = re.findall(r'\[[^\]]+\](?:\.\.\.)?|<[^>]+>(?:\.\.\.)?|[^\s]+', syntax)
        positionals: list[PositionalSpec] = []
        indices_by_name: dict[str, int] = {}

        for token in usage_tokens:
            positional = cls._parse_usage_positional(token)
            if positional is None:
                continue

            existing_index = indices_by_name.get(positional.api_name)
            if existing_index is None:
                indices_by_name[positional.api_name] = len(positionals)
                positionals.append(positional)
                continue

            existing = positionals[existing_index]
            positionals[existing_index] = PositionalSpec(
                name=existing.name,
                api_name=existing.api_name,
                value_type=existing.value_type,
                required=existing.required or positional.required,
                multiple=existing.multiple or positional.multiple,
                help=existing.help,
            )

        return positionals

    @classmethod
    def _parse_positionals(
        cls,
        entries_by_section: dict[str, list[tuple[str, str]]],
        usage_text: str,
        usage_path: tuple[str, ...],
        subcommands: list[str],
    ) -> list[PositionalSpec]:
        entries: list[tuple[str, str]] = []

        for section_name in cls._POSITIONAL_SECTIONS:
            entries.extend(entries_by_section.get(section_name, []))

        if entries:
            return cls._parse_positionals_from_entries(entries, usage_text, subcommands)

        return cls._parse_positionals_from_usage(usage_text, usage_path)

    @classmethod
    def _parse_command_sections(
        cls,
        entries_by_section: dict[str, list[tuple[str, str]]],
        usage_path: tuple[str, ...],
        usage_text: str,
        subcommands: list[str],
    ) -> list[ParsedCommandSection]:
        if not usage_path:
            return []

        candidate_names = (usage_path[-1].lower(), ' '.join(usage_path).lower())
        sections: list[ParsedCommandSection] = []

        for section_name in dict.fromkeys(candidate_names):
            entries = entries_by_section.get(section_name)
            if not entries:
                continue
            positionals = cls._parse_positionals_from_entries(entries, usage_text, subcommands)
            options = cls._parse_options_from_entries(entries)
            if not positionals and not options:
                continue
            sections.append(
                ParsedCommandSection(
                    name=usage_path[-1],
                    positionals=tuple(positionals),
                    options=tuple(options),
                )
            )

        return sections

    def parse(self, text: str) -> ParsedHelp:
        lines = text.splitlines()
        usage_text = self._usage_text(lines)
        usage_path = self._usage_path(lines)
        entries_by_section = self._collect_section_entries(lines)
        subcommands = self._parse_subcommands(lines, entries_by_section)

        return ParsedHelp(
            summary=self._find_summary(lines),
            usage_path=usage_path,
            subcommands=tuple(subcommands),
            positionals=tuple(
                self._parse_positionals(
                    entries_by_section,
                    usage_text,
                    usage_path,
                    subcommands,
                )
            ),
            options=tuple(self._parse_options(entries_by_section)),
            command_sections=tuple(
                self._parse_command_sections(
                    entries_by_section,
                    usage_path,
                    usage_text,
                    subcommands,
                )
            ),
        )

    def to_command_spec(
        self,
        parsed_help: ParsedHelp,
        command_path: tuple[str, ...],
    ) -> CommandSpec:
        command_section = None
        if command_path:
            command_section = self._find_command_section(parsed_help, command_path[-1])

        positionals = parsed_help.positionals
        options = parsed_help.options

        if command_section is not None:
            section_positionals = {
                positional.api_name: positional
                for positional in command_section.positionals
            }
            positionals = tuple(
                section_positionals.get(positional.api_name, positional)
                for positional in positionals
            )
            existing_names = {positional.api_name for positional in positionals}
            positionals = (
                *positionals,
                *(
                    positional
                    for positional in command_section.positionals
                    if positional.api_name not in existing_names
                ),
            )
            options = (*options, *command_section.options)

        return CommandSpec(
            path=command_path,
            summary=parsed_help.summary,
            positionals=positionals,
            options=options,
        )

    def to_primary_command_spec(
        self,
        parsed_help: ParsedHelp,
        command_path: tuple[str, ...],
    ) -> CommandSpec | None:
        if command_path or len(parsed_help.usage_path) != 1:
            return None

        command_name = parsed_help.usage_path[0]

        if self._find_command_section(parsed_help, command_name) is None:
            return None

        return self.to_command_spec(parsed_help, (command_name,))
