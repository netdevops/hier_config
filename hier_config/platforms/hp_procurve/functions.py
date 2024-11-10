def hp_procurve_expand_range(interface_range_str: str) -> tuple[str, ...]:
    """Expand interface ranges like 1/2-5,2/22-45."""
    interfaces: list[str] = []
    for interface_range in interface_range_str.split(","):
        _hp_procurve_expand_range_segment(interface_range, interfaces)
    if len(frozenset(interfaces)) != len(interfaces):
        message = (
            "the length of frozenset(interfaces) was not the same as len(interfaces)"
        )
        raise ValueError(message)
    return tuple(interfaces)


def _hp_procurve_expand_range_segment(
    interface_range: str,
    interfaces: list[str],
) -> None:
    start_stop = interface_range.split("-")
    if len(start_stop) != 2:
        interfaces.append(start_stop[0])
        return

    start_port_prefix = ""
    trk = "Trk"
    if start_stop[0].startswith(trk):
        stack_member = trk
        start_port_number = start_stop[0].removeprefix(trk)
        end_port_number = start_stop[1].removeprefix(trk)
    elif "/" in start_stop[0]:
        stack_member, start_port_number = start_stop[0].split("/")
        stack_member += "/"
        end_port_number = start_stop[1].split("/")[-1]
        # account for `interface 5/A1`
        for letter in ("A", "B", "C", "D"):
            if start_port_number.startswith(letter):
                start_port_prefix = letter
                start_port_number = start_port_number.removeprefix(letter)
                if not end_port_number.startswith(letter):
                    message = f"{letter=}, the end_port_number should start with the same letter"
                    raise ValueError(message)
                end_port_number = end_port_number.removeprefix(letter)
                break
    else:
        stack_member = ""
        start_port_number = start_stop[0]
        end_port_number = start_stop[1]

    interfaces.extend(
        f"{stack_member}{start_port_prefix}{port}"
        for port in range(int(start_port_number), int(end_port_number) + 1)
    )
