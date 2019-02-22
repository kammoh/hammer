#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  stackup.py
#  Data structures to represent technology stackup options
#
#  See LICENSE for licence details.

from enum import Enum
from typing import Any, Callable, Iterable, List, NamedTuple, Optional, Tuple, Dict
from hammer_utils import reverse_dict

class RoutingDirection(Enum):
    Vertical = 1
    Horizontal = 2
    Redistribution = 3

    @classmethod
    def __mapping(cls) -> Dict[str, "RoutingDirection"]:
        return {
            "vertical": RoutingDirection.Vertical,
            "horizontal": RoutingDirection.Horizontal,
            "redistribution": RoutingDirection.Redistribution
        }

    @staticmethod
    def from_str(input_str: str) -> "RoutingDirection":
        try:
            return RoutingDirection.__mapping()[input_str]
        except KeyError:
            raise ValueError("Invalid routing direction: " + str(input_str))

    def __str__(self) -> str:
        return reverse_dict(RoutingDirection.__mapping())[self]

    def opposite(self) -> "RoutingDirection":
        if self == RoutingDirection.Vertical:
            return RoutingDirection.Horizontal
        elif self == RoutingDirection.Horizontal:
            return RoutingDirection.Vertical
        else:
            return self

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
# index: The order in the stackup (lower is closer to the substrate)
# direction: The preferred routing direction of this metal layer, or "redistribution" for non-routing top-level redistribution metals like Aluminum
# min_width: The minimum wire width for this layer
# pitch: The minimum cross-mask pitch for this layer (NOT same-mask pitch for multiply-patterned layers)
# offset: The routing track offset from the origin for the first track in this layer (0 = first track is on an axis)
# power_strap_widths_and_spacings: A list of WidthSpacingTuples that specify the minimum spacing rules for an infinitely long wire of variying width
class Metal(NamedTuple('Metal', [
    ('name', str),
    ('index', int),
    ('direction', "RoutingDirection"),
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
            direction=RoutingDirection.from_str(d["direction"]),
            min_width=float(d["min_width"]),
            pitch=float(d["pitch"]),
            offset=float(d["offset"]),
            power_strap_widths_and_spacings=sorted(list(map(lambda x: WidthSpacingTuple.from_setting(x), list(d["power_strap_widths_and_spacings"]))), key=lambda x: x.width_at_least)
        )

    def get_spacing_for_width(self, width: float) -> float:
        spacing = 0.0
        for wst in self.power_strap_widths_and_spacings:
            if width >= wst.width_at_least:
                spacing = max(spacing, wst.min_spacing)
            else:
                # The list is sorted so we can early-out
                return spacing
        return spacing

    def min_spacing_from_pitch(self, pitch: float) -> float:
        ws = self.power_strap_widths_and_spacings
        spacing = ws[0].min_spacing
        # We take the width_at_least of tuple N and the spacing of tuple N+1
        # For example:
        #   W   S
        #   0   1
        #   4   2
        #   7   3
        #
        #   a line of width 4 must have spacing 2, for a pitch of 6
        #   a line of width 3.999 can have spacing 1, for a pitch of 4.999
        #   so we check if pitch is less than W(N+1) + S(N) = 4 + 1 = 5
        #   to be sure we can use S(N) which is 1
        for first, second in zip(ws[:-1], ws[1:]):
            if pitch >= (first.min_spacing + second.width_at_least):
                spacing = second.min_spacing
        return spacing

    # This method will return the maximum width a wire can be to consume a given number of routing tracks
    # This assumes the neighbors of the wide wire are minimum-width routes
    # i.e. T W T
    # T = thin / min-width
    # W = wide
    # Returns width, spacing and start
    def get_width_spacing_start_twt(self, tracks: int) -> Tuple[float, float, float]:
        ws = self.power_strap_widths_and_spacings
        s2w = (tracks + 1) * self.pitch - self.min_width
        spacing = ws[0].min_spacing
        for first, second in zip(ws[:-1], ws[1:]):
            if s2w >= (2*first.min_spacing + second.width_at_least):
                spacing = second.min_spacing
        width = s2w - spacing*2
        # TODO this is assuming that a manufacturing grid is 0.001
        assert (int(self.min_width * 1000) % 2 == 0), "Assuming all min widths are even here, if not fix me"
        start = self.min_width / 2 + spacing
        return (width, spacing, start)

    # This method will return the maximum width a wire can be to consume a given number of routing tracks
    # This assumes both neighbors are wires of the same width
    # i.e. W W W
    # T = thin / min-width
    # W = wide
    # Returns width, spacing, and start
    def get_width_spacing_start_www(self, tracks: int, force_even=False) -> Tuple[float, float, float]:
        raise NotImplementedError("Not yet implemented")

    # This method will return the maximum width a wire can be to consume a given number of routing tracks
    # This assumes one neighbor is a min width wire, and the other is the same size as this (mirrored)
    # i.e. T W W T
    # T = thin / min-width
    # W = wide
    # Returns width, spacing, and offset
    # The offset is the offset of the wire centerline to the track (odd number of tracks) or half-track (even number of tracks)
    # Positive numbers towards min-width wire
    def get_width_spacing_start_twwt(self, tracks: int, force_even=False) -> Tuple[float, float, float]:
        ws = self.power_strap_widths_and_spacings
        s3w2 = (2 * tracks + 1) * self.pitch - self.min_width
        spacing = ws[0].min_spacing
        for first, second in zip(ws[:-1], ws[1:]):
            if s3w2 >= (3*first.min_spacing + 2*second.width_at_least):
                spacing = second.min_spacing
        width = (s3w2 - spacing*3)/2
        start = self.min_width / 2 + spacing
        # TODO this is assuming that a manufacturing grid is 0.001
        # Note the rounding here seems to get around some floating-point roundoff issues in prior calculations
        if force_even and ((int(round(width * 1000)) % 2) != 0):
                width = width - 0.001
                start = start + 0.001
        return (width, spacing, start)

    # TODO implement M W X* W M style wires, where X is slightly narrower than W and centered on-grid

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

