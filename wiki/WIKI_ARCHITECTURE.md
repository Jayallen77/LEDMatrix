# Architecture

DisplayController selects retained managers and owns one DisplayManager. Weather, markets, Calendar, Colorado sports, and music refresh off the drawing path. Non-music checks are paced at 20 Hz. RuntimeReporter publishes health on a separate worker; the local dashboard only reads preview/status and saves validated settings. See [cleanup notes](../docs/CLEANUP_NOTES.md).
