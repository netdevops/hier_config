"""Helpers for parsing Ruckus/Brocade FastIron interface specifications."""

from __future__ import annotations

PORT_KEYWORDS = frozenset({"ethe", "ethernet"})


def _expand_port_pair(start: str, stop: str) -> tuple[str, ...]:
    """Expand ``1/1/1`` .. ``1/1/48`` into every port id in between.

    Only the trailing port field varies in a FastIron range: the unit and slot
    fields must match, and the port field must be a non-negative integer at
    both ends. Anything else is not something we can enumerate exactly, so it
    raises and the caller leaves the line untouched. The check runs before the
    conversion so every failure carries one of this helper's own messages
    rather than one from ``int()``; it uses ``str.isdecimal`` rather than
    ``str.isdigit`` because the latter also accepts characters ``int()``
    rejects, such as superscripts.
    """
    start_parts = start.split("/")
    stop_parts = stop.split("/")
    if len(start_parts) != len(stop_parts) or len(start_parts) not in {2, 3}:
        message = f"unsupported port range {start!r} to {stop!r}"
        raise ValueError(message)
    if start_parts[:-1] != stop_parts[:-1]:
        message = f"port range {start!r} to {stop!r} spans multiple slots"
        raise ValueError(message)

    if not (start_parts[-1].isdecimal() and stop_parts[-1].isdecimal()):
        message = f"unsupported port range {start!r} to {stop!r}"
        raise ValueError(message)

    first = int(start_parts[-1])
    last = int(stop_parts[-1])
    if last < first:
        message = f"reversed port range {start!r} to {stop!r}"
        raise ValueError(message)

    prefix = "/".join(start_parts[:-1])
    return tuple(f"{prefix}/{port}" for port in range(first, last + 1))


def fastiron_expand_ports(words: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    """Expand a FastIron port specification into individual port ids.

    ``ethe 1/1/1 to 1/1/3 ethe 1/2/4`` becomes
    ``("1/1/1", "1/1/2", "1/1/3", "1/2/4")``.

    Raises ``ValueError`` on anything that does not parse cleanly so callers can
    leave the original line alone rather than silently dropping ports.
    """
    ports: list[str] = []
    index = 0
    while index < len(words):
        word = words[index]
        if word not in PORT_KEYWORDS:
            message = f"unexpected token {word!r} in port specification"
            raise ValueError(message)
        index += 1
        if index >= len(words):
            message = "port specification ended after a port keyword"
            raise ValueError(message)
        start = words[index]
        index += 1
        if index < len(words) and words[index] == "to":
            index += 1
            if index >= len(words):
                message = "port range ended after 'to'"
                raise ValueError(message)
            ports.extend(_expand_port_pair(start, words[index]))
            index += 1
        else:
            ports.append(start)

    if not ports:
        message = "empty port specification"
        raise ValueError(message)
    return tuple(dict.fromkeys(ports))
