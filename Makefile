VERSION := $(shell grep '__version__' src/app.py | cut -d'"' -f2)

.PHONY: run build dmg release clean

run:
	uv run python src/app.py

build:
	uv run python setup.py py2app
	@echo "Built dist/BBC Alert.app"

dmg: build
	create-dmg \
		--volname "BBC Alert" \
		--window-pos 200 120 \
		--window-size 600 400 \
		--icon-size 128 \
		--icon "BBC Alert.app" 160 185 \
		--hide-extension "BBC Alert.app" \
		--app-drop-link 430 185 \
		"dist/BBC-Alert-$(VERSION).dmg" \
		"dist/BBC Alert.app"
	@echo "Created dist/BBC-Alert-$(VERSION).dmg"

release: dmg
	gh release create v$(VERSION) \
		"dist/BBC-Alert-$(VERSION).dmg" \
		--title "BBC Alert v$(VERSION)" \
		--generate-notes
	@echo "Released v$(VERSION)"

clean:
	rm -rf build dist
