# Windows PE resource recovery v5

The verified executable's PE `.rsrc` section contains six true PNG icon resources at 16, 24, 32, 48, 64 and 256 pixels. The six images were combined according to the embedded RT_GROUP_ICON structure into an ICO file. The version resource reports CompanyName `Gurizon`, ProductName/FileDescription `Asistan`, FileVersion/ProductVersion `0.1.5`, and LegalCopyright `2026 Gurizon / Postuby, Inc.`. The 334-byte application manifest declares the Windows Common Controls v6 dependency.

The extractor validates the original EXE SHA-256 before using fixed file offsets, checks each PNG signature and validates that the ICO group references the expected sizes. It writes a manifest containing byte lengths and SHA-256 hashes.

The v5 archive was independently regenerated and compared byte-for-byte against nine outputs: six PNGs, the combined ICO, the raw VERSIONINFO resource and the application manifest. All nine matched.

This recovers Windows resources, not the missing Rust/Tauri backend or the full build project.
