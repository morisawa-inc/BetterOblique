BUNDLE = BetterOblique.glyphsFilter
DEPS := $(BUNDLE)/Contents/Resources/site-packages/beziers/__init__.py

.PHONY: all
all: $(BUNDLE)

.PHONY: $(BUNDLE)
$(BUNDLE): $(DEPS) $(BUNDLE)/Contents/_CodeSignature/CodeResources

SRC := $(shell find $(BUNDLE) -name '*.py')
$(BUNDLE)/Contents/_CodeSignature/CodeResources: $(SRC)
	find $(BUNDLE) -name '*.pyc' -type f -exec rm '{}' \;
	-find $(BUNDLE) -name '__pycache__' -type d -exec rm -r '{}' \;
	command -v postbuild-codesign $(BUNDLE) >/dev/null 2>&1 && postbuild-codesign $(BUNDLE) 
	command -v postbuild-notarize $(BUNDLE) >/dev/null 2>&1 && postbuild-notarize $(BUNDLE)

.PHONY: clean
clean: 
	rm -rf $(BUNDLE)/Contents/_CodeSignature build/beziers $(BUNDLE)/Contents/Resources/site-packages

PATCHES := $(wildcard patches/*.patch)

build/beziers/__init__.py:
	mkdir -p build
	pip install --no-binary :all: --no-deps --target build beziers==0.1.0
	rm -r build/beziers/__pycache__
	git apply --directory=build $(PATCHES)

$(BUNDLE)/Contents/Resources/site-packages/beziers/__init__.py: build/beziers/__init__.py
	mkdir -p "$(dir $@)"
	cp -R $(wildcard $(dir $<)*) "$(dir $@)"
