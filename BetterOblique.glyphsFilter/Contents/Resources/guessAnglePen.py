from __future__ import division

from fontTools.pens.basePen import AbstractPen

import math
import collections

import sys
import os

if os.path.join(os.path.dirname(__file__), 'site-packages') not in sys.path:
    sys.path.append(os.path.join(os.path.dirname(__file__), 'site-packages'))

from fontPens.flattenPen import FlattenPen


Movement = collections.namedtuple('Movement', ('distance', 'angle'))

class GuessAnglePen(AbstractPen):
    
    def __init__(self, threshold=25.0):
        self._recursive = False
        self._pen = FlattenPen(self)
        self._movements = []
        self._last_point = None
        self.threshold = abs(threshold)
        self.angle = None
        
    def moveTo(self, pt):
        self.angle = None
        if not self._recursive:
            self._recursive = True
            self._pen.moveTo(pt)
            self._recursive = False
            return
        self.append_movement(pt)
        self._last_point = pt

    def lineTo(self, pt):
        if not self._recursive:
            self._recursive = True
            self._pen.lineTo(pt)
            self._recursive = False
            return
        self.append_movement(pt)
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
        self.needs_update_angle()
        self._movements = []
        self._last_point = None

    def endPath(self):
        if not self._recursive:
            self._recursive = True
            self._pen.endPath()
            self._recursive = False
            return
        self.needs_update_angle()
        self._movements = []
        self._last_point = None
        
    def addComponent(self, glyphName, transformation):
        if not self._recursive:
            self._recursive = True
            self._pen.addComponent(glyphName, transformation)
            self._recursive = False
            return
    
    def append_movement(self, pt):
        if self._last_point is not None:
            distance = math.hypot(abs(pt[0] - self._last_point[0]), abs(pt[1] - self._last_point[1]))
            angle = None
            if pt[1] - self._last_point[1] == 0:
                angle = 0.0
            elif pt[0] - self._last_point[0] == 0:
                angle = math.pi / 2.0
            else:
                angle = math.atan((pt[1] - self._last_point[1]) / (pt[0] - self._last_point[0]))
            movement = Movement(distance, angle)
            self._movements.append(movement)
    
    @staticmethod
    def mean_angle_from_movements(movements):
        c = sum((math.cos(m.angle) * m.distance for m in movements))
        s = sum((math.sin(m.angle) * m.distance for m in movements))
        return math.atan(s / c)
    
    @classmethod
    def is_radian_in_range(cls, rad, min_rad, max_rad):
        if min_rad > max_rad: 
            return (0 <= rad <= min_rad) and (max_rad <= rad <= math.pi * 2.0)
        return min_rad <= rad <= max_rad
    
    def needs_update_angle(self):
        total_distance = sum((m.distance for m in self._movements))
        if total_distance > 0:
            mean_angle1 = self.mean_angle_from_movements(self._movements)
            threshold = math.radians(self.threshold)
            min_angle = mean_angle1 - threshold
            max_angle = mean_angle1 + threshold
            filtered_movements = [m for m in self._movements if self.is_radian_in_range(m.angle, min_angle, max_angle)]
            if len(filtered_movements) > 0:
                mean_angle2 = self.mean_angle_from_movements(filtered_movements)
                self.angle = mean_angle2
