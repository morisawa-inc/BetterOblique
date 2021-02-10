# -*- coding: utf-8 -*-

from __future__ import division, print_function, unicode_literals

import objc
from GlyphsApp import *
from GlyphsApp.plugins import *
from AppKit import NSTextField, NSValueBinding, NSObservedObjectKey, NSObservedKeyPathKey, NSOptionsKey, NSContinuouslyUpdatesValueBindingOption

import sys
import os
if os.path.join(os.path.dirname(__file__), 'site-packages') not in sys.path:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'site-packages'))
from betterObliqueFilter import shear_layer
del sys.path[0]

import math


class BetterObliqueFilterSteppingTextField(NSTextField):
    
    stepper = objc.IBOutlet()
    
    def textView_doCommandBySelector_(self, textView, selector):
        selector_multiplier_dict = {
            'moveUp:': 1.0,
            'moveUpAndModifySelection:': 10.0,
            'moveDown:': -1.0,
            'moveDownAndModifySelection:': -10.0
        }
        if selector in selector_multiplier_dict:
            stepper = self.stepper
            increment = stepper.increment() * selector_multiplier_dict[selector]
            value = self.doubleValue() + increment
            value = max(stepper.minValue(), min(stepper.maxValue(), value))
            self.setDoubleValue_(value)
            if self.isContinuous():
                self.validateEditing()
            info = self.infoForBinding_(NSValueBinding)
            if info:
                target  = info.valueForKey_(NSObservedObjectKey)
                keyPath = info.valueForKey_(NSObservedKeyPathKey)
                options = info.valueForKey_(NSOptionsKey)
                if target and keyPath and options and options.get(NSContinuouslyUpdatesValueBindingOption):
                    target.setValue_forKeyPath_(self.doubleValue(), keyPath)
            editor = self.currentEditor()
            if editor:
                editor.didChangeText()
            return True
        return False

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
    
    def strengthFactor(self):
        return Glyphs.defaults['jp.co.morisawa.BetterOblique.strengthFactor'] or 0
    
    def setStrengthFactor_(self, value):
        value = int(value)
        if value != Glyphs.defaults['jp.co.morisawa.BetterOblique.strengthFactor']:
            self.willChangeValueForKey_('strengthFactor')
            Glyphs.defaults['jp.co.morisawa.BetterOblique.strengthFactor'] = int(value)
            self.didChangeValueForKey_('strengthFactor')
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
    
    def shouldApplyWithoutSkewing(self):
        return Glyphs.boolDefaults['jp.co.morisawa.BetterOblique.shouldApplyWithoutSkewing'] or False
    
    def setShouldApplyWithoutSkewing_(self, value):
        value = bool(value)
        if value != Glyphs.boolDefaults['jp.co.morisawa.BetterOblique.shouldApplyWithoutSkewing']:
            self.willChangeValueForKey_('shouldApplyWithoutSkewing')
            Glyphs.defaults['jp.co.morisawa.BetterOblique.shouldApplyWithoutSkewing'] = bool(value)
            self.didChangeValueForKey_('shouldApplyWithoutSkewing')
            self.update()

    @objc.python_method
    def settings(self):
        self.menuName = Glyphs.localize({'en': 'Better Oblique'})
        self.loadNib('IBdialog', __file__)

    @objc.python_method
    def start(self):
        Glyphs.registerDefault('jp.co.morisawa.BetterOblique.opticalCorrection', 1)
        Glyphs.registerDefault('jp.co.morisawa.BetterOblique.strengthFactor', 0)
        Glyphs.registerDefault('jp.co.morisawa.BetterOblique.shouldKeepCenter', True)
        Glyphs.registerDefault('jp.co.morisawa.BetterOblique.shouldApplyWithoutSkewing', False)

        self.setAngle_(self.angle())
        self.setOpticalCorrection_(self.opticalCorrection())
        self.setStrengthFactor_(self.strengthFactor())
        self.setShouldKeepCenter_(self.shouldKeepCenter())
        self.setShouldApplyWithoutSkewing_(self.shouldApplyWithoutSkewing())
        
        self._final = False
        
    def final(self):
        self._final = True
    
    def process_(self, sender):
        super(BetterObliqueFilter, self).process_(sender)
        self._final = False
    
    @objc.python_method
    def filter(self, layer, inEditView, customParameters):
        
        # This filter is painfully slow for batch processing, and making a preview is too expensive.
        # When the custom parameter dict is empty and multiple glyphs are selected in the font view,
        # execute the transformation only right after the user presses the apply button in the dialog.
        if not customParameters and not inEditView:
            if len(Glyphs.font.selection) > 1:
                if not self._final:
                    return
        
        font = layer.parent.parent
        master_dict = dict(((master.id, master) for master in font.masters))
        master = master_dict.get(layer.layerId, master_dict.get(layer.associatedMasterId))
        
        std_vw, std_hw = (40.0, 40.0)
        if master.verticalStems and len(master.verticalStems) > 0:
            std_vw = master.verticalStems[0]
        if master.horizontalStems and len(master.horizontalStems) > 0:
            std_hw = master.horizontalStems[0]
        shear_angle = math.radians(customParameters.get('angle', self.angle()))
        optical_correction = ('none', 'thin', 'medium', 'thick')[customParameters.get('opticalCorrection', self.opticalCorrection())]
        strength = (10.0 - customParameters.get('strengthFactor', self.strengthFactor())) / 10.0
        keep_center = customParameters.get('keepCenter', self.shouldKeepCenter())
        skip_shear = customParameters.get('applyWithoutSkewing', self.shouldApplyWithoutSkewing())
        
        shear_layer(layer, shear_angle, std_vw=std_vw, std_hw=std_hw, optical_correction=optical_correction, strength=strength, center=keep_center, skip_shear=skip_shear)
    
    @objc.python_method
    def generateCustomParameter(self):
        return "{0}; angle:{1}; opticalCorrection:{2}; strengthFactor:{3}; keepCenter:{4}; applyWithoutSkewing:{5}".format(
            self.__class__.__name__,
            self.angle() or 0.0,
            self.opticalCorrection() or 0,
            self.strengthFactor() or 0,
            1 if self.shouldKeepCenter() else 0,
            1 if self.shouldApplyWithoutSkewing() else 0
            )

    @objc.python_method
    def __file__(self):
        return __file__
