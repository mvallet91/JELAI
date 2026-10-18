# Course materials

Put the files for your students in this folder: notebooks, datasets and
other documents. Folders are allowed.

- When a student notebook server starts, JELAI copies every file from this
  folder to the work directory of the student.
- A file that the student already has is never replaced, so the work of the
  student is safe. To give a changed version of a file to all students, use a
  new file name.
- New files reach a student the next time the notebook server of that student
  starts.

## Start notebook

To open a notebook for each student after login, copy `course.yaml.example`
to `course.yaml` and set the path of the notebook:

```yaml
start_notebook: Task1.ipynb
```

The path is relative to the work directory. The hub reads the file each time
a notebook server starts, so a restart of the hub is not necessary. If the
file or the key is missing, students see the JupyterLab launcher.

## Requirement

The `.env` file must contain `COURSE_MATERIALS_DIR`, the absolute path of this
folder. `setup.sh` sets it.
