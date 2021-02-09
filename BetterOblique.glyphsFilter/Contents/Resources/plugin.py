# -*- coding: utf-8 -*-

from __future__ import division, print_function, unicode_literals

import objc
from GlyphsApp import *
from GlyphsApp.plugins import *

from AppKit import NSOnState, NSOffState

from betterObliqueFilter import shear_layer

class BetterObliqueFilter(FilterWithDialog):
    
    dialog = objc.IBOutlet()

    def angle(self):
        return Glyphs.defaults['TransformSlant'] or 0.0
    
    def setAngle_(self, value):
        value = float(value)
        if value != Glyphs.defaults['TransformSlant']:
            self.willChangeValueForKey_('angle')
            Glyphs.defaults['TransformSlant'] = value
            self.didChangeValueForKey_('angle')
            self.update()

    def opticalCorrection(self):
        return Glyphs.defaults['jp.co.morisawa.BetterOblique.opticalCorrection'] or 0
    
    def setOpticalCorrection_(self, value):
        value = int(value)
        if value != Glyphs.defaults['jp.co.morisawa.BetterOblique.opticalCorrection']:
            self.willChangeValueForKey_('opticalCorrection')
            Glyphs.defaults['jp.co.morisawa.BetterOblique.opticalCorrection'] = int(value)
            self.didChangeValueForKey_('opticalCorrection')
            self.update()
    
    def shouldIgnoreClockwisePaths(self):
        return Glyphs.boolDefaults['jp.co.morisawa.BetterOblique.shouldIgnoreClockwisePaths'] or False
    
    def setShouldIgnoreClockwisePaths_(self, value):
        value = bool(value)
        if value != Glyphs.boolDefaults['jp.co.morisawa.BetterOblique.shouldIgnoreClockwisePaths']:
            self.willChangeValueForKey_('shouldIgnoreClockwisePaths')
            Glyphs.defaults['jp.co.morisawa.BetterOblique.shouldIgnoreClockwisePaths'] = bool(value)
            self.didChangeValueForKey_('shouldIgnoreClockwisePaths')
            self.update()
    
    def shouldKeepCenter(self):
        return Glyphs.boolDefaults['jp.co.morisawa.BetterOblique.shouldKeepCenter'] or False
    
    def setShouldKeepCenter_(self, value):
        value = bool(value)
        if value != Glyphs.boolDefaults['jp.co.morisawa.BetterOblique.shouldKeepCenter']:
            self.willChangeValueForKey_('shouldKeepCenter')
            Glyphs.defaults['jp.co.morisawa.BetterOblique.shouldKeepCenter'] = bool(value)
            self.didChangeValueForKey_('shouldKeepCenter')
            self.update()

    @objc.python_method
    def settings(self):
        self.menuName = Glyphs.localize({'en': 'Better Oblique'})
        self.loadNib('IBdialog', __file__)

    @objc.python_method
    def start(self):
        Glyphs.registerDefault('jp.co.morisawa.BetterOblique.opticalCorrection', 1)
        Glyphs.registerDefault('jp.co.morisawa.BetterOblique.shouldIgnoreClockwisePaths', False)
        Glyphs.registerDefault('jp.co.morisawa.BetterOblique.shouldKeepCenter', True)
        self.setAngle_(self.angle())
        self.setOpticalCorrection_(self.opticalCorrection())
        self.setShouldIgnoreClockwisePaths_(self.shouldIgnoreClockwisePaths())
        self.setShouldKeepCenter_(self.shouldKeepCenter())
    
    @objc.python_method
    def filter(self, layer, inEditView, customParameters):
        font = layer.parent.parent
        master = font.masters[layer.layerId]
        shear_angle = customParameters.get('angle', self.angle())
        optical_correction = ('none', 'thin', 'medium', 'thick')[customParameters.get('opticalCorrection', self.opticalCorrection())]
        ignore_clockwise = customParameters.get('ignoreClockwise', self.shouldIgnoreClockwisePaths())
        use_cursify_as_fallback = ignore_clockwise
        keep_center = customParameters.get('keepCenter', self.shouldKeepCenter())
        shear_layer(layer, shear_angle, optical_correction=optical_correction, ignore_clockwise=ignore_clockwise, use_cursify_as_fallback=use_cursify_as_fallback, hstems=master.horizontalStems, vstems=master.verticalStems, center=keep_center)
    
    @objc.python_method
    def generateCustomParameter(self):
        return "{0}; angle:{1}; opticalCorrection:{2}; ignoreClockwise:{3}; keepCenter:{4};".format(
            self.__class__.__name__,
            self.angle() or 0.0,
            self.opticalCorrection() or 0,
            1 if self.shouldIgnoreClockwisePaths() else 0,
            1 if self.shouldKeepCenter() else 0
            )

    @objc.python_method
    def __file__(self):
        return __file__
