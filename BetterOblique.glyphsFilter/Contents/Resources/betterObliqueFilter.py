# -*- coding: utf-8 -*-

from __future__ import division

import beziers.point
import beziers.path
import beziers.line
import beziers.cubicbezier
import beziers.affinetransformation

from fontTools.pens.pointPen import SegmentToPointPen

import math
import cmath

from GlyphsApp import *
from GlyphsApp.plugins import *

def mean_angle(*radians):
    # Averages/Mean angle - Rosetta Code
    # https://rosettacode.org/wiki/Averages/Mean_angle#Python
    return cmath.phase(sum(cmath.rect(1, rad) for rad in radians) / len(radians))

def lli8(x1, y1, x2, y2, x3, y3, x4, y4):
    nx = (x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)
    ny = (x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)
    d  = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if d == 0:
        return None
    return beziers.point.Point(nx / d, ny / d)

def lli4(p1, p2, p3, p4):
    return lli8(p1.x, p1.y, p2.x, p2.y, p3.x, p3.y, p4.x, p4.y)

def line_line_intersection(segment1, segment2):
    # A Primer on Bézier Curves - Implementing line-line intersections
    # https://pomax.github.io/bezierinfo#intersections
    return lli4(segment1[0], segment1[-1], segment2[0], segment2[-1])

def gradual_distance_from_angle(dx, dy, angle):
    ratio = abs((angle % math.pi) / (math.pi / 2.0))
    return (1.0 - ratio) * dx + ratio * dy

def shear_matrix(shear_angle, vertical=False):
    if vertical:
        return ((1, 0, 0), (math.tan(shear_angle), 1, 0), (0, 0, 1))
    return ((1, math.tan(shear_angle), 0), (0, 1, 0), (0, 0, 1))

def expected_stem_scale(stem_angle, shear_angle, stem_size=1.0, vertical=False):
    # Make a stem with the given angle, and return the width after transformation.
    segment = beziers.line.Line(beziers.point.Point(0.0, 0.0), beziers.point.Point(0.0, stem_size))
    segment = segment.rotated(beziers.point.Point(0.0, 0.0), stem_angle)
    segment = segment.transformed(beziers.affinetransformation.AffineTransformation(shear_matrix(shear_angle, vertical=vertical)))
    return segment.length / stem_size

def target_stem_scale(shear_angle, vertical=False, mode=None):
    if mode == 'thick':
        return 1.0 / expected_stem_scale(0.0, shear_angle, vertical=vertical)
    elif mode == 'thin':
        return 1.0 / expected_stem_scale(math.pi / 2.0, shear_angle, vertical=vertical)
    elif mode == 'thinnest':
        return 1.0 / expected_stem_scale(math.pi - shear_angle, shear_angle, vertical=vertical)
    return 1.0 / ((expected_stem_scale(0.0, shear_angle, vertical=vertical) + expected_stem_scale(math.pi / 2.0, shear_angle, vertical=vertical)) / 2.0)

def angle_diff(a, b):
    return math.atan2(math.sin(b - a), math.cos(b - a))

def make_distance_vector(d):
    if isinstance(d, (int, float)):
        d = beziers.point.Point(d, d)
    elif isinstance(d, (tuple, list)):
        d = beziers.point.Point(d[0], d[1])
    return d

def join_cubic_bezier_segments(s1, s2, use_glyphs=True):
    assert(s1[3] == s2[0])
    # Glyphs applies more sophisticated curve fitting when removing a node.
    if use_glyphs:
        layer = GSLayer()
        pen = layer.getPen()
        pen.moveTo((s1[0].x, s1[0].y))
        pen.curveTo((s1[1].x, s1[1].y), (s1[2].x, s1[2].y), (s1[3].x, s1[3].y))
        pen.curveTo((s2[1].x, s2[1].y), (s2[2].x, s2[2].y), (s2[3].x, s2[3].y))
        pen.endPath()
        path = layer.paths[0]
        assert(path.nodes[3].type == CURVE)
        path.removeNodeCheckKeepShape_(path.nodes[3])
        p = beziers.point.Point(path.nodes[1].x, path.nodes[1].y)
        q = beziers.point.Point(path.nodes[2].x, path.nodes[2].y)
        return beziers.cubicbezier.CubicBezier(s1[0], p, q, s2[3])
    # Approximate the two cubic bezier segments according to the following approach:
    #   Retrieve the initial cubic Bézier curve subdivided in two Bézier curves - Mathematics Stack Exchange
    #   https://math.stackexchange.com/questions/877725/retrieve-the-initial-cubic-bézier-curve-subdivided-in-two-bézier-curves
    # However, the approximation doesn't look good enough to maintain the thickness after offsetting in general.
    # The way defcon joins segments when deleting nodes looks similar, thus it doesn't help me either:
    #   defcon/Lib/defcon/tools/bezierMath.py
    #   https://github.com/robotools/defcon/blob/master/Lib/defcon/tools/bezierMath.py#L12
    k = s2[1].distanceFrom(s2[0]) / s1[2].distanceFrom(s1[3])
    p = s1[1] * (1 + k) - s1[0] * k
    q = (s2[2] * (1 + k) - s2[3]) / k
    return beziers.cubicbezier.CubicBezier(s1[0], p, q, s2[3])

def offset_path(path, distance, subdivide=True, curve_segments_only=False):
    
    segments = path.asSegments()
    original_number_of_segments = len(segments)
    
    # Make a function that returns a offset distance.
    if isinstance(distance, (int, float)):
        distance = (distance, distance)
    if not callable(distance):
        dx, dy = distance[0], distance[1]
        def constant_distance_func(segment, index, count):
            return beziers.point.Point(dx, dy)
        distance = constant_distance_func

    # Add a midpoint to each steep curve to compensate errors when offsetting.
    original_points_in_segments = None 
    if subdivide:
        original_points_in_segments = set()
        for segment in segments:
            original_points_in_segments.add(segment[0])
            original_points_in_segments.add(segment[-1])
        needs_split = True
        pass_in_progress = 1 # FIXME: splitting at extrema seems to create funky joins.
        while needs_split:
            splitted_segments = []
            has_splitted = False
            for i, segment in enumerate(segments):
                has_performed_split_in_segment = False
                if isinstance(segment, beziers.cubicbezier.CubicBezier):
                    if pass_in_progress > 0:
                        # Keep splitting at midpoint if the curvature is still steep.
                        mid_point = segment.pointAtTime(0.5)
                        start_angle, end_angle = beziers.line.Line(segment[0], mid_point).endAngle, beziers.line.Line(mid_point, segment[-1]).startAngle
                        if abs(angle_diff(start_angle, end_angle)) > math.radians(20.0):
                            splitted_segments.extend(segment.splitAtTime(0.5))
                            has_performed_split_in_segment = True
                    elif pass_in_progress == 0:
                        # Pomax recommends to split at extrema of each segment as a first pass.
                        #   Curve offsetting - A Primer on Bézier Curves
                        #   https://pomax.github.io/bezierinfo/#offsetting
                        extrema_times = segment.findExtremes()
                        if extrema_times and len(extrema_times) > 0:
                            t0 = 0.0
                            sub_segment_to_be_splitted = segment
                            for t1 in sorted(extrema_times):
                                splitted_sub_segments = sub_segment_to_be_splitted.splitAtTime(t1 - t0)
                                splitted_segments.append(splitted_sub_segments[0])
                                sub_segment_to_be_splitted = splitted_sub_segments[1]
                                t0 = t1
                            splitted_segments.append(sub_segment_to_be_splitted)
                            has_performed_split_in_segment = True
                if not has_performed_split_in_segment:
                    splitted_segments.append(segment)
                has_splitted = has_splitted or has_performed_split_in_segment
            segments = splitted_segments
            needs_split = has_splitted or pass_in_progress == 0
            pass_in_progress += 1
    
    number_of_segments = len(segments)
    
    # Offset paths based on the approximation proposed by Tiller and Hanson. Each corner will have a miter joint.
    #   Control points of offset bezier curve - Mathematics Stack Exchange
    #   https://math.stackexchange.com/questions/465782/control-points-of-offset-bezier-curve
    translation_dict = {}
    for i in range(number_of_segments):
        s1, s2 = segments[i], segments[(i + 1) % number_of_segments]
        d1 = make_distance_vector(distance(s1.endAngle,   i, number_of_segments))
        d2 = make_distance_vector(distance(s2.startAngle, i, number_of_segments))
        d0 = make_distance_vector(distance(mean_angle(s1.endAngle, s2.startAngle), i, number_of_segments))
        if True:
            if not curve_segments_only or s2[0] not in original_points_in_segments:
                p1  = s2[0]
                s1a = s1.endAngle - math.pi / 2.0
                s1e = beziers.point.Point(s1[-1].x + math.cos(s1a) * d1.x, s1[-1].y + math.sin(s1a) * d1.y)
                s2a = s2.startAngle - math.pi / 2.0
                s2s = beziers.point.Point(s2[0].x  + math.cos(s2a) * d2.x, s2[0].y  + math.sin(s2a) * d2.y)
                t1  = beziers.line.Line(s1e, s1e + s1.tangentAtTime(1.0))
                t2  = beziers.line.Line(s2s, s2s + s2.tangentAtTime(0.0))
                p2  = line_line_intersection(t1, t2)
                # Give up miter join if the angle is too steep.
                if p2 is None or s1.endAngle == s2.startAngle or abs(math.degrees(angle_diff(s2.startAngle, s1.endAngle))) < 8.0:
                    nominal_angle = mean_angle(s1.endAngle, s2.startAngle) - math.pi / 2.0
                    p2 = beziers.point.Point(p1.x + math.cos(nominal_angle) * d0.x, p1.y + math.sin(nominal_angle) * d0.y)
                translation_dict[p1] = p2
        if isinstance(s1, beziers.cubicbezier.CubicBezier):
            # Always offset BCPs in subdivided segments when curve_segments_only is on.
            if not curve_segments_only or s1[3] not in original_points_in_segments:
                nominal_angle = mean_angle(beziers.line.Line(s1[1], s1[2]).endAngle, beziers.line.Line(s1[2], s1[3]).startAngle) - math.pi / 2.0
                p1 = s1[2]
                p2 = beziers.point.Point(p1.x + math.cos(nominal_angle) * d1.x, p1.y + math.sin(nominal_angle) * d1.y)
                translation_dict[p1] = p2
        if isinstance(s2, beziers.cubicbezier.CubicBezier):
            # Always offset BCPs in subdivided segments when curve_segments_only is on.
            if not curve_segments_only or s2[0] not in original_points_in_segments:
                nominal_angle = mean_angle(beziers.line.Line(s2[0], s2[1]).endAngle, beziers.line.Line(s2[1], s2[2]).startAngle) - math.pi / 2.0
                p1 = s2[1]
                p2 = beziers.point.Point(p1.x + math.cos(nominal_angle) * d2.x, p1.y + math.sin(nominal_angle) * d2.y)
                translation_dict[p1] = p2
        
    # Find subdivided points and store their translated points into a set.
    if subdivide:
        translated_points_to_be_removed = set()
        for original_point, translated_point in translation_dict.items():
            if original_point not in original_points_in_segments:
                translated_points_to_be_removed.add(translated_point)
    
    # Translate points in all segments.
    new_segments = []
    for segment in segments:
        if isinstance(segment, beziers.cubicbezier.CubicBezier):
            new_segments.append(beziers.cubicbezier.CubicBezier(translation_dict.get(segment[0], segment[0]), translation_dict.get(segment[1], segment[1]), translation_dict.get(segment[2], segment[2]), translation_dict.get(segment[3], segment[3])))
        elif isinstance(segment, beziers.line.Line):
            new_segments.append(beziers.line.Line(translation_dict.get(segment[0], segment[0]), translation_dict.get(segment[1], segment[1])))
    segments = new_segments
    
    # Remove subdivided points.
    if subdivide:
        while len(segments) > original_number_of_segments:
            new_segments = []
            skip_next = False
            number_of_segments = len(segments)
            for i in range(number_of_segments):
                if skip_next:
                    skip_next = False
                    continue
                s1, s2 = segments[i], segments[(i + 1) % number_of_segments]
                if s1[-1] in translated_points_to_be_removed:
                    if isinstance(s1, beziers.cubicbezier.CubicBezier) and isinstance(s2, beziers.cubicbezier.CubicBezier):
                        s1 = join_cubic_bezier_segments(s1, s2)
                        skip_next = True
                    else:
                        s1 = beziers.cubicbezier.Line(s1[0], s2[-1])
                        skip_next = True
                new_segments.append(s1)
            segments = new_segments
    
    return beziers.path.BezierPath.fromSegments(segments)

def draw(path, pen):
    segments = path.asSegments()
    if len(segments) > 0:
        pen.moveTo((segments[0][0].x, segments[0][0].y))
        for segment in segments:
            if isinstance(segment, beziers.line.Line):
                pen.lineTo((segment[1].x, segment[1].y))
            elif isinstance(segment, beziers.cubicbezier.CubicBezier):
                pen.curveTo((segment[1].x, segment[1].y), (segment[2].x, segment[2].y), (segment[3].x, segment[3].y))
        if path.closed:
            pen.closePath()

def draw_points(path, point_pen):
    draw(path, SegmentToPointPen(point_pen))

def make_bezier_path_from_glyphs_path(gspath):
    layer = GSLayer()
    layer.paths.append(gspath.copy())
    return beziers.path.BezierPath.fromGlyphsLayer(layer)[0]

def offset_glyphs_path(gspath, distance):
    layer = GSLayer()
    path = offset_path(make_bezier_path_from_glyphs_path(gspath), distance)
    draw_points(path, layer.getPointPen())
    gspath.nodes = layer.paths[0].nodes

def shear_path(path, shear_angle, std_vw, std_hw, mode='medium', strength=1.0, curve_segments_only=False, vertical=False, skip_shear=False):

    def distance_func(angle, index, count):
        stem_angle = angle + math.pi / 2.0
        stem_scale = target_stem_scale(shear_angle, vertical=vertical, mode=mode) / expected_stem_scale(stem_angle, shear_angle, vertical=vertical)
        stem_width = gradual_distance_from_angle(std_vw, std_hw, stem_angle)
        stem_diff  = ((stem_width - stem_width * stem_scale) / 2.0) * strength
        return stem_diff
    
    if mode != 'none':
        path = offset_path(path, distance_func, curve_segments_only=curve_segments_only)
    
    if not skip_shear:
        t = beziers.affinetransformation.AffineTransformation(shear_matrix(shear_angle, vertical=vertical))
        path = beziers.path.BezierPath.fromSegments([s.transformed(t) for s in path.asSegments()])
    
    return path

def shear_gspath(gspath, shear_angle, std_vw, std_hw, mode='medium', strength=1.0, curve_segments_only=False, vertical=False, skip_shear=False):
    layer = GSLayer()
    path = shear_path(make_bezier_path_from_glyphs_path(gspath), shear_angle, std_vw, std_hw, mode=mode, strength=strength, curve_segments_only=curve_segments_only, vertical=vertical, skip_shear=skip_shear)
    draw_points(path, layer.getPointPen())
    if len(layer.paths) > 0 and layer.paths[0]:
        gspath.nodes = layer.paths[0].nodes

#

def shear_layer(layer, shear_angle, std_vw=40.0, std_hw=40.0, optical_correction='medium', strength=1.0, curve_segments_only=False, vertical=False, center=True, skip_shear=False):
    if std_vw is None or std_hw is None:
        raise ValueError('StdVW and StdHW need to be defined to run this filter.')
    orig_bounds = layer.bounds
    for path in layer.paths:
        shear_gspath(path, shear_angle, std_vw, std_hw, mode=optical_correction, strength=strength, curve_segments_only=curve_segments_only, vertical=vertical, skip_shear=skip_shear)
    new_bounds = layer.bounds
    if center:
        orig_center = (orig_bounds.origin.x + orig_bounds.size.width / 2.0, orig_bounds.origin.y + orig_bounds.size.height / 2.0)
        new_center  = (new_bounds.origin.x  + new_bounds.size.width / 2.0,  new_bounds.origin.y  + new_bounds.size.height / 2.0)
        offset = (orig_center[0] - new_center[0], orig_center[1] - new_center[1])
        for path in layer.paths:
            path.applyTransform((1.0, 0.0, 0.0, 1.0, offset[0], offset[1]))
