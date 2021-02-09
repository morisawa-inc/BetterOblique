BUNDLE = GuessAndFixPathDirection.glyphsFilter

.PHONY: all
all: $(BUNDLE)/Contents/_CodeSignature/CodeResources

.PHONY: $(BUNDLE)
$(BUNDLE): $(BUNDLE)/Contents/_CodeSignature/CodeResources

SRC := $(shell find $(BUNDLE) -name '*.py')
$(BUNDLE)/Contents/_CodeSignature/CodeResources: $(SRC)
	find $(BUNDLE) -name '*.pyc' -type f -exec rm '{}' \;
	command -v postbuild-codesign $(BUNDLE) >/dev/null 2>&1 && postbuild-codesign $(BUNDLE) 
	command -v postbuild-notarize $(BUNDLE) >/dev/null 2>&1 && postbuild-notarize $(BUNDLE)

.PHONY: clean
clean: 
	rm -rf $(BUNDLE)/Contents/_CodeSignature

.PHONY: sampler
sampler: test/data/ContourDirectionTestCase.glyphs
	test/sampler.py $<
	mogrify -resize x512 0*.png
