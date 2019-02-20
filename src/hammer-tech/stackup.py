#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  stackup.py
#  Data structures to represent technology stackup options
#
#  See LICENSE for licence details.

from typing import Any, Callable, Iterable, List, NamedTuple, Optional, Tuple, Dict

# Note to maintainers: This is mirrored in schema.json- don't change one without the other

# A tuple of wire width limit and spacing for generating a piecewise linear rule for spacing based on wire width
# width_at_least: Any wires larger than this must obey the minSpacing rule
# min_spacing: The minimum spacing for this bin. If a wire is wider than multiple entries, the worst-case (larger) minSpacing wins.
class WidthSpacingTuple(NamedTuple('WidthSpacingTuple', [
    ('width_at_least', float),
    ('min_spacing', float)
])):
    __slots__ = ()

    @staticmethod
    def from_setting(d: dict) -> "WidthSpacingTuple":
        return WidthSpacingTuple(
            width_at_least=float(d["width_at_least"]),
            min_spacing=float(d["min_spacing"])
        )

# A metal layer and some basic info about it
# name: M1, M2, etc.
# index: The order in the stackup (lower # is closer to the wafer)
# direction: The preferred routing direction of this metal layer, or "redistribution" for non-routing top-level redistribution metals like Aluminum
# min_width: The minimum wire width for this layer
# pitch: The minimum cross-mask pitch for this layer (NOT same-mask pitch for multiply-patterned layers)
# offset: The routing track offset from the origin for the first track in this layer (0 = first track is on an axis)
# power_strap_widths_and_spacings: A list of WidthSpacingTuples that specify the minimum spacing rules for an infinitely long wire of variying width
class Metal(NamedTuple('Metal', [
    ('name', str),
    ('index', int),
    ('direction', str), # TODO enum
    ('min_width', float),
    ('pitch', float),
    ('offset', float),
    ('power_strap_widths_and_spacings', List[WidthSpacingTuple])
])):
    __slots__ = ()

    @staticmethod
    def from_setting(d: dict) -> "Metal":
        return Metal(
            name=str(d["name"]),
            index=int(d["index"]),
            direction=str(d["direction"]),
            min_width=float(d["min_width"]),
            pitch=float(d["pitch"]),
            offset=float(d["offset"]),
            power_strap_widths_and_spacings=list(map(lambda x: WidthSpacingTuple.from_setting(x), list(d["power_strap_widths_and_spacings"])))
        )

    def get_spacing_for_width(self, width: float) -> float:
        spacing = 0.0
        for wst in self.power_strap_widths_and_spacings:
            if width >= wst.width_at_least:
                spacing = max(spacing, wst.min_spacing)
        return spacing

# For now a stackup is just a list of metals with a meaningful keyword name
# TODO add vias, etc. when we need them
class Stackup(NamedTuple('Stackup', [
    ('name', str),
    ('metals', List[Metal])
])):
    __slots__ = ()

    @staticmethod
    def from_setting(d: dict) -> "Stackup":
        return Stackup(
            name=str(d["name"]),
            metals=list(map(lambda x: Metal.from_setting(x), list(d["metals"])))
        )


    def get_metal(self, name: str) -> "Metal":
        # TODO don't brute force this
        for m in self.metals:
            if m.name == name:
                return m
        raise ValueError("Metal named %s is not defined in stackup %s" % (name, self.name))

