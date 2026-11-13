# On main, `make build` writes the signed shortcuts to the repo root (commit them).
# On any other branch it writes them to build/ (git-ignored) with the installer and a
# per-run refresh step pointing at that branch's SW_DLT.py (see scripts/branch_build.py),
# so branch builds can never be committed or merged by accident.
BRANCH ?= $(shell git rev-parse --abbrev-ref HEAD)
OUT := $(if $(filter main,$(BRANCH)),.,build)
SHORTCUTS := SW-DLT SW-DLT-Audio SW-DLT-Video-720p
SIGN = shortcuts sign --mode people-who-know-me

.PHONY: verify test check-urls build release release-meta test-shortcut clean

verify:
	@python3 scripts/verify_shortcut_shell.py

test:
	@python3 -m unittest discover -s tests

check-urls:
	@python3 scripts/check_branch_urls.py --branch main

build: verify
	@python3 scripts/generate_quick_shortcuts.py
	@mkdir -p build/tmp $(OUT)
	@for name in $(SHORTCUTS); do \
	  python3 scripts/branch_build.py "$(BRANCH)" "src/$$name.plist" "build/tmp/$$name.shortcut" && \
	  $(SIGN) --input "build/tmp/$$name.shortcut" --output "$(OUT)/$$name.shortcut" && \
	  echo "signed $(OUT)/$$name.shortcut" || exit 1; \
	done
	@rm -rf build/tmp

# Production build from any branch: same output as `make build` on main (repo root,
# script from main), so a release can be prepared in the feature PR itself. On macOS
# the built files are opened in Shortcuts for import (choose Replace, not Keep Both:
# a renamed "SW-DLT 2" would break the quick shortcuts and the download callback).
release:
	@$(if $(FORCE),,python3 scripts/set_release_meta.py --check-bump)
	@$(MAKE) --no-print-directory build BRANCH=main
	@if command -v open >/dev/null && [ "$$(uname)" = Darwin ]; then \
	  for name in $(SHORTCUTS); do open "$$name.shortcut"; done; \
	  echo; echo "Opened in Shortcuts: import each one, choosing Replace if asked."; \
	fi
	@echo "Next: make release-meta   (asks you to copy each iCloud link in Shortcuts and reads the clipboard)"

# Writes api/updates/latest.json + release_links.json for the plist version and validates them.
# Links/notes not passed as MAIN= AUDIO= VIDEO= NOTES= are asked for (links via the clipboard).
release-meta:
	@python3 scripts/set_release_meta.py $(if $(MAIN),--main "$(MAIN)") $(if $(AUDIO),--audio "$(AUDIO)") $(if $(VIDEO),--video "$(VIDEO)") $(if $(NOTES),--notes "$(NOTES)")

test-shortcut:
	@mkdir -p build/tmp
	@cp src/SW-DLT-OutputTest.plist build/tmp/SW-DLT-OutputTest.shortcut
	@$(SIGN) --input build/tmp/SW-DLT-OutputTest.shortcut --output build/SW-DLT-OutputTest.shortcut
	@rm -rf build/tmp
	@echo "signed build/SW-DLT-OutputTest.shortcut"

clean:
	@rm -rfv build
