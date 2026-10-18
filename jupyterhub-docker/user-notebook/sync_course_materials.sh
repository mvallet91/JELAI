#!/bin/bash
# Copy the course materials of the teacher into the work directory of the
# student. Files that already exist are never replaced, so the work of the
# student is safe. The files course.yaml and README.md stay out.
SOURCE="${COURSE_MATERIALS_MOUNT:-/srv/course_materials}"
TARGET="${1:-/home/jovyan/work}"

if [ -d "$SOURCE" ]; then
    mkdir -p "$TARGET"
    for entry in "$SOURCE"/* "$SOURCE"/.[!.]*; do
        [ -e "$entry" ] || continue
        case "$(basename "$entry")" in
            course.yaml|README.md|.gitkeep) continue ;;
        esac
        cp -rn "$entry" "$TARGET"/ 2>/dev/null || true
    done
fi
exit 0
