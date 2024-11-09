def expand_range(number_range_str: str) -> tuple[int, ...]:
    """Expand ranges like 2-5,8,22-45."""
    numbers: list[int] = []
    for number_range in number_range_str.split(","):
        start_stop = number_range.split("-")
        if len(start_stop) == 2:
            start = int(start_stop[0])
            stop = int(start_stop[1])
            numbers.extend(n for n in range(start, stop + 1))
        else:
            numbers.append(int(start_stop[0]))
    assert len(set(numbers)) == len(numbers)
    return tuple(numbers)
