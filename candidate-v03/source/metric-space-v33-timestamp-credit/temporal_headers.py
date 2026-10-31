"""Reversible adjacent identical timestamp references; raw bodies stay intact."""
from datetime import datetime
import re

FULL = re.compile(r'\[([A-Za-z_]+) \| ([^\[\]|\r\n]+)\] ')
SAME = re.compile(r'\[([A-Za-z_]+) \| same timestamp as previous item\] ')


def full_header(header):
    match = FULL.fullmatch(header)
    if not match:
        return None
    role, stamp = match.groups()
    try:
        value = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    if value.tzinfo is None:
        return None
    return role, stamp


def compact_units(units):
    output = []
    previous = None
    for unit in units:
        parsed = full_header(unit['header'])
        header = unit['header']
        if parsed and previous == parsed[1]:
            header = '['+parsed[0]+' | same timestamp as previous item] '
        output.append({**unit, 'header': header})
        previous = parsed[1] if parsed else None
    if expand_units(output) != units:
        raise ValueError('Timestamp-reference round trip failed; preserve original units')
    return output


def expand_units(units):
    output = []
    previous = None
    for unit in units:
        header = unit['header']
        same = SAME.fullmatch(header)
        parsed = full_header(header)
        if same:
            if previous is None:
                raise ValueError('Timestamp reference has no preceding timestamp')
            header = '['+same[1]+' | '+previous+'] '
        else:
            previous = parsed[1] if parsed else None
        output.append({**unit, 'header': header})
    return output
