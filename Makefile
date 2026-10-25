build:
	@python3 scripts/generate_quick_shortcuts.py
	@cp -v src/SW-DLT.plist SW-DLT-unsigned.shortcut
	@shortcuts sign --mode people-who-know-me --input "SW-DLT-unsigned.shortcut" --output "SW-DLT.shortcut"
	@rm SW-DLT-unsigned.shortcut
	@cp -v src/SW-DLT-Audio.plist SW-DLT-Audio-unsigned.shortcut
	@shortcuts sign --mode people-who-know-me --input "SW-DLT-Audio-unsigned.shortcut" --output "SW-DLT-Audio.shortcut"
	@rm SW-DLT-Audio-unsigned.shortcut
	@cp -v src/SW-DLT-Video-720p.plist SW-DLT-Video-720p-unsigned.shortcut
	@shortcuts sign --mode people-who-know-me --input "SW-DLT-Video-720p-unsigned.shortcut" --output "SW-DLT-Video-720p.shortcut"
	@rm SW-DLT-Video-720p-unsigned.shortcut
clean:
	@rm -fvf SW-DLT-unsigned.shortcut SW-DLT.shortcut SW-DLT-Audio-unsigned.shortcut SW-DLT-Audio.shortcut SW-DLT-Video-720p-unsigned.shortcut SW-DLT-Video-720p.shortcut
