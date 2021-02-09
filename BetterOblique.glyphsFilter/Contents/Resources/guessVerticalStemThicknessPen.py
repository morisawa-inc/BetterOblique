from __future__ import division

from fontTools.pens.basePen import AbstractPen

import math

import sys
import os

if os.path.join(os.path.dirname(__file__), 'site-packages') not in sys.path:
    sys.path.append(os.path.join(os.path.dirname(__file__), 'site-packages'))

from fontPens.flattenPen import FlattenPen


class GuessVerticalStemThicknessPen(AbstractPen):
    
    def __init__(self):
        self._recursive = False
        self._pen = FlattenPen(self)
        self._segments = []
        self._last_point = None
        self._leftmost_point = None
        self._rightmost_point = None
        self.thickness = None
        
    def moveTo(self, pt):
        self.thickness = None
        if not self._recursive:
            self._recursive = True
            self._pen.moveTo(pt)
            self._recursive = False
            return
        self.add_segment(pt)
        self._last_point = pt

    def lineTo(self, pt):
        if not self._recursive:
            self._recursive = True
            self._pen.lineTo(pt)
            self._recursive = False
            return
        self.add_segment(pt)
        self._last_point = pt

    def curveTo(self, *points):
        if not self._recursive:
            self._recursive = True
            self._pen.curveTo(*points)
            self._recursive = False
            return
        raise NotImplentedError

    def qCurveTo(self, *points):
        if not self._recursive:
            self._recursive = True
            self._pen.qCurveTo(*points)
            self._recursive = False
            return
        raise NotImplentedError

    def closePath(self):
        if not self._recursive:
            self._recursive = True
            self._pen.closePath()
            self._recursive = False
            return
        self.needs_update_thickness()
        self.reset()

    def endPath(self):
        if not self._recursive:
            self._recursive = True
            self._pen.endPath()
            self._recursive = False
            return
        self.needs_update_thickness()
        self.reset()
        
    def addComponent(self, glyphName, transformation):
        if not self._recursive:
            self._recursive = True
            self._pen.addComponent(glyphName, transformation)
            self._recursive = False
            return

    def add_segment(self, pt):
        if self._last_point is not None:
            self._segments.append((self._last_point, pt))
        if self._leftmost_point is None or self._leftmost_point[0] > pt[0]:
            self._leftmost_point = pt
        if self._rightmost_point is None or self._rightmost_point[0] < pt[0]:
            self._rightmost_point = pt

    @staticmethod
    def intersection_of_segments(s1, s2):
        # Find an intersection of the two given lines:
        #   https://pomax.github.io/bezierinfo/#intersections
        def _(x1, y1, x2, y2, x3, y3, x4, y4):
            nx = (x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)
            ny = (x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)
            d  = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
            return (nx / d, ny / d) if d != 0 else None
        return _(s1[0][0], s1[0][1], s1[1][0], s1[1][1], s2[0][0], s2[0][1], s2[1][0], s2[1][1])
    
    def reset(self):
        self._segments = []
        self._last_point = None
        self._leftmost_point = None
        self._rightmost_point = None

    def needs_update_thickness(self):
        thicknesses = []
        if len(self._segments) >= 4 and self._leftmost_point and self._rightmost_point:
            extreme_points_in_interest = []
            for collected_segment in self._segments:
                for collected_point in collected_segment:
                    if collected_point[0] == self._leftmost_point[0] or collected_point[0] == self._rightmost_point[0]:
                        extreme_points_in_interest.append(collected_point)
            for extreme_point_in_interest in extreme_points_in_interest:
                distances = []
                horizontal_segment_from_extreme = (extreme_point_in_interest, (extreme_point_in_interest[0] + 1.0, extreme_point_in_interest[1]))
                for collected_segment in self._segments:
                    if collected_segment[0] != extreme_point_in_interest and collected_segment[1] != extreme_point_in_interest:
                        y1, y2 = (collected_segment[0][1], collected_segment[1][1])
                        if y1 > y2:
                            y1, y2 = (y2, y1)
                        if y1 <= extreme_point_in_interest[1] <= y2:
                            p1 = extreme_point_in_interest
                            p2 = self.intersection_of_segments(horizontal_segment_from_extreme, collected_segment)
                            distance = abs(math.hypot(p1[0] - p2[0], p1[1] - p2[1]))
                            distances.append(distance)
                if len(distances) > 0:
                    thicknesses.append(min(distances))
        if len(thicknesses) > 0:
            self.thickness = min(thicknesses)
