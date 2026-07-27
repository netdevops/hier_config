def expand_range(number_range_str: str) -> tuple[int, ...]:
    """Expand ranges like ``2-5,8,22-45`` into a de-duplicated, ordered tuple.

    Overlapping/duplicated ids (e.g. ``10,10-12``) collapse to a single entry
    rather than raising, so callers that split a collapsed line get the set of
    ids the operator meant. A malformed segment -- non-numeric, or more than one
    ``-`` such as ``1-2-3`` -- raises ``ValueError`` instead of silently
    truncating, so callers can leave the original line untouched.
    """
    numbers: list[int] = []
    for number_range in number_range_str.split(","):
        start_stop = number_range.split("-")
        if len(start_stop) == 1:
            numbers.append(int(start_stop[0]))
        elif len(start_stop) == 2:
            start = int(start_stop[0])
            stop = int(start_stop[1])
            if stop < start:
                message = (
                    f"reversed range segment {number_range!r} in {number_range_str!r}"
                )
                raise ValueError(message)
            numbers.extend(range(start, stop + 1))
        else:
            message = f"invalid range segment {number_range!r} in {number_range_str!r}"
            raise ValueError(message)
    return tuple(dict.fromkeys(numbers))


def convert_to_set_commands(config_raw: str) -> str:
    """Convert a Juniper style config string into a list of set commands.

    Args:
        config_raw (str): The config string to convert to set commands
    Returns:
        config_raw (str): Configuration string

    """
    lines = config_raw.split("\n")
    path: list[str] = []
    set_commands: list[str] = []

    for line in lines:
        stripped_line = line.strip()

        # Skip empty lines
        if not stripped_line:
            continue

        # Strip ; from the end of the line
        stripped_line = stripped_line.removesuffix(";")

        # Count the number of spaces at the beginning to determine the level
        level = line.find(stripped_line) // 4

        # Adjust the current path based on the level
        path = path[:level]

        # If the line ends with '{' or '}', it starts a new block
        if stripped_line.endswith(("{", "}")):
            path.append(stripped_line[:-1].strip())
        elif stripped_line.startswith(("set", "delete")):
            # It's already a set command, so just add it to the list
            set_commands.append(stripped_line)
        else:
            # It's a command line, construct the full command
            command = f"set {' '.join(path)} {stripped_line}"
            set_commands.append(command)

    return "\n".join(set_commands)
