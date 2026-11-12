# On main, `make build` writes the signed shortcuts to the repo root (commit them).
# On any other branch it writes them to build/ (git-ignored) with the installer and a
# per-run refresh step pointing at that branch's SW_DLT.py (see scripts/branch_build.py),
# so branch builds can never be committed or merged by accident.
BRANCH ?= $(shell git rev-parse --abbrev-ref HEAD)
OUT := $(if $(filter main,$(BRANCH)),.,build)
SHORTCUTS := SW-DLT SW-DLT-Audio SW-DLT-Video-720p
SIGN = shortcuts sign --mode people-who-know-me

.PHONY: verify test check-urls build test-shortcut clean

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

test-shortcut:
	@mkdir -p build/tmp
	@cp src/SW-DLT-OutputTest.plist build/tmp/SW-DLT-OutputTest.shortcut
	@$(SIGN) --input build/tmp/SW-DLT-OutputTest.shortcut --output build/SW-DLT-OutputTest.shortcut
	@rm -rf build/tmp
	@echo "signed build/SW-DLT-OutputTest.shortcut"

clean:
	@rm -rfv build
