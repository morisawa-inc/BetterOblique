from __future__ import division

from fontTools.pens.areaPen import AreaPen

from guessAnglePen import GuessAnglePen
from guessVerticalStemThicknessPen import GuessVerticalStemThicknessPen

import math
import collections

from Cocoa import NSPoint, NSContainsRect

from GlyphsApp import *
from GlyphsApp.plugins import *

PathStatistics = collections.namedtuple('PathStatistics', ('path', 'angle', 'area'))

def make_path_statistics(path):
    if False:
        pen = StatisticsPen()
        path.draw(pen)
        return PathStatistics(path, pen.slant, pen.area)
    else:
        guess_angle_pen = GuessAnglePen()
        area_pen = AreaPen()
        path.draw(guess_angle_pen)
        path.draw(area_pen)
        return PathStatistics(path, guess_angle_pen.angle, area_pen.value)

def make_upright_path_statistics(base_path_statistics):
    if base_path_statistics.angle is None:
        return None
    new_path = base_path_statistics.path.copy()
    t = math.pi / 2.0 + base_path_statistics.angle # Make it upright regardless
    new_path.applyTransform((math.cos(t), -math.sin(t), math.sin(t), math.cos(t), 0.0, 0.0))
    return make_path_statistics(new_path)

def calc_path_complexity(upright_path_statics):
    path = upright_path_statics.path
    bounds_area = path.bounds.size.width * path.bounds.size.height
    path_area = abs(upright_path_statics.area)
    complexity = 1.0 - (path_area / bounds_area)
    return complexity

#

def intersection_of_segments(s1, s2):
    # Find an intersection of the two given lines:
    #   https://pomax.github.io/bezierinfo/#intersections
    def _(x1, y1, x2, y2, x3, y3, x4, y4):
        nx = (x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)
        ny = (x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)
        d  = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        return (nx / d, ny / d) if d != 0 else None
    return _(s1[0][0], s1[0][1], s1[1][0], s1[1][1], s2[0][0], s2[0][1], s2[1][0], s2[1][1])

def calc_rotated_segment(s, angle):
    # Rotate a line by 90 degrees:
    #  https://en.wikipedia.org/wiki/Rotation_matrix#In_two_dimensions
    x, y = (s[1][0] - s[0][0], s[1][1] - s[0][1])
    rx = x * math.cos(angle) - y * math.sin(angle)
    ry = x * math.sin(angle) + y * math.cos(angle)
    return (s[0], NSPoint(s[0][0] + rx, s[0][1] + ry))

def calc_thickness_of_rectangular_path(path):
    # Find the longest and seemingly parallel lines of the given rectangular path.
    # Rotate one of the lines by 90 degrees and find the intersections.
    # Calculate the distance of the points and that will be the thickness we need.
    if len(path.segments) == 4:
        tuple_segments = (((s[0].x, s[0].y), (s[1].x, s[1].y)) for s in path.segments)
        sorted_segments = list(sorted(tuple_segments, key=lambda s: -abs(math.hypot(s[1][0] - s[0][0], s[1][1] - s[0][1]))))
        s1, s2 = (sorted_segments[0], sorted_segments[1])
        rs = calc_rotated_segment(s1, (math.pi / 2.0))
        i1, i2 = (intersection_of_segments(s1, rs), intersection_of_segments(s2, rs))
        d = abs(math.hypot(i2[0] - i1[0], i2[1] - i1[1]))
        return d
    return None

def calc_thickness_after_shear(rotate_radians, shear_radians, width=1000.0, height=1.0):
    # Make a closed rectangle path.
    path = GSPath()
    path.nodes.append(GSNode((0.0,   0.0),    LINE))
    path.nodes.append(GSNode((width, 0.0),    LINE))
    path.nodes.append(GSNode((width, height), LINE))
    path.nodes.append(GSNode((0.0,   height), LINE))
    path.closed = True
    # Apply a shear after rotation.
    path.applyTransform((math.cos(rotate_radians), -math.sin(rotate_radians), math.sin(rotate_radians), math.cos(rotate_radians), 0.0, 0.0))
    path.applyTransform((1.0, 0.0, -math.tan(shear_radians), 1.0, 0.0, 0.0))
    # Calculate the thickness of the transformed path.
    return calc_thickness_of_rectangular_path(path)

def calc_thickness_after_shear_in_degree(rotate_angle=0.0, shear_angle=36.0, width=1000.0, height=1.0):
    return calc_thickness_after_shear(rotate_radians, shear_radians, width, height)

"""
if __name__ == '__main__':
    # Find out the resulted diagonal stem thickness after applying a shear effect.
    # The line is upright when the angle equals to 90, and horizontal when 0 or 180.
    for angle in range(0, 180 + 1):
        print(angle, calc_sheared_thickness(rotate_angle=angle, shear_angle=36.0))
"""

#

def closed_paths_from_selected_nodes_in_layer(layer):
    for path in layer.paths:
        new_path = GSPath()
        for node in path.nodes:
            if node.selected:
                new_path.nodes.append(node.copy())
        new_path.closed = True
        yield new_path

def offset_path_horizontally(path, amount):
    def find_filter_instance_by_name(name):
        for instance in Glyphs.filters:
            if instance.__class__.__name__ == name:
                return instance
    layer = GSLayer()
    layer.paths.append(path.copy())
    orig_height = path.bounds.size.height
    offset_curve_filter = find_filter_instance_by_name('GlyphsFilterOffsetCurve')
    offset_curve_filter.processLayer_withArguments_(layer, ['GlyphsFilterOffsetCurve', str(amount), '0.0', '0', '0.5', 'keep'])
    new_height = layer.paths[0].bounds.size.height
    offset_y = -(new_height - orig_height) / 2.0 if new_height > orig_height else 0.0
    layer.paths = []
    layer.paths.append(path.copy())
    offset_curve_filter.processLayer_withArguments_(layer, ['GlyphsFilterOffsetCurve', str(amount), str(offset_y), '0', '0.5', 'keep'])
    return layer.paths[0]
    
def calc_vstem_width_in_path(path):
    pen = GuessVerticalStemThicknessPen()
    path.draw(pen)
    return pen.thickness

def calc_target_thickness(mode, shear_radians):
    if mode == 'thick':
        return 1.0
    elif mode == 'thin':
        return calc_thickness_after_shear(math.pi / 2.0, shear_radians, width=1000.0, height=1)
    return (calc_thickness_after_shear(math.pi / 2.0, shear_radians, width=1000.0, height=1) + 1.0) / 2.0

def is_clockwise_related_path(path, layer=None):
    if path.direction > 0:
        return True
    if layer:
        clockwise_paths = [p for p in layer.paths if p.direction > 0]
        for clockwise_path in clockwise_paths:
            if NSContainsRect(path.bounds, clockwise_path.bounds):
                return True
    return False

def apply_cursify_slant_to_path(path, hstems, vstems, shear_angle):
    if path and hstems and vstems:
        font = GSFont()
        font.masters[0].horizontalStems = hstems
        font.masters[0].verticalStems   = vstems
        glyph = GSGlyph('A')
        font.glyphs.append(glyph)
        glyph.layers[0].paths.append(path.copy())
        glyph.layers[0].doSlantingCorrectionWithAngle_Origin_(shear_angle, (0, 0))
        path.nodes = glyph.layers[0].paths[0].nodes

def shear_path(path, shear_angle, optical_correction='medium', ignore_clockwise=False, use_cursify_as_fallback=False, layer=None, hstems=None, vstems=None):
    if optical_correction and optical_correction != 'none':
        has_corrected = False
        if not ignore_clockwise or not is_clockwise_related_path(path, layer):
            base_path_statistics    = make_path_statistics(path)
            upright_path_statistics = make_upright_path_statistics(base_path_statistics)
            if upright_path_statistics:
                complexity = calc_path_complexity(upright_path_statistics)
                if complexity < 0.8:
                    if upright_path_statistics.path.bounds.size.width * (16.0 / 9.0) < upright_path_statistics.path.bounds.size.height:
                        shear_radians = math.radians(shear_angle)
                        expected_thickness = calc_thickness_after_shear(base_path_statistics.angle, shear_radians, width=1000.0, height=1)
                        target_thickness = calc_target_thickness(optical_correction, shear_radians)
                        scale_x = target_thickness / expected_thickness
                        upright_path  = upright_path_statistics.path
                        upright_width = calc_vstem_width_in_path(upright_path) or upright_path.bounds.size.width
                        offset_x = (upright_width * scale_x - upright_width) / 2.0
                        scaled_path = offset_path_horizontally(upright_path, offset_x)
                        t = -(math.pi / 2.0 + base_path_statistics.angle)
                        scaled_path.applyTransform((math.cos(t), -math.sin(t), math.sin(t), math.cos(t), 0.0, 0.0))
                        path.nodes = scaled_path.nodes
                        has_corrected = True
        if not has_corrected and use_cursify_as_fallback:
            apply_cursify_slant_to_path(path, hstems, vstems, shear_angle)
    shear_radians = math.radians(-shear_angle)
    path.applyTransform((1.0, 0.0, -math.tan(shear_radians), 1.0, 0.0, 0.0))

def shear_layer(layer, shear_angle, optical_correction='medium', ignore_clockwise=False, use_cursify_as_fallback=False, hstems=None, vstems=None, center=True):
    orig_bounds = layer.bounds
    for path in layer.paths:
        shear_path(path, shear_angle, optical_correction=optical_correction, ignore_clockwise=ignore_clockwise, use_cursify_as_fallback=use_cursify_as_fallback, hstems=hstems, vstems=vstems)
    new_bounds = layer.bounds
    if center:
        orig_center_x = orig_bounds.origin.x + orig_bounds.size.width / 2.0
        new_center_x  = new_bounds.origin.x  + new_bounds.size.width / 2.0
        offset_x = orig_center_x - new_center_x
        for path in layer.paths:
            path.applyTransform((1.0, 0.0, 0.0, 1.0, offset_x, 0.0))
