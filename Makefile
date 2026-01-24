build:
	@cp -v src/SW-DLT.plist SW-DLT-unsigned.shortcut
	@shortcuts sign --mode people-who-know-me --input "SW-DLT-unsigned.shortcut" --output "SW-DLT.shortcut"
	@rm SW-DLT-unsigned.shortcut
clean:
	@rm -fvf SW-DLT-unsigned.shortcut SW-DLT.shortcut
