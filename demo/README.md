# Demo course

A small course for a demonstration of JELAI with one student and one
teacher. It uses Task 1 (Shark Inventory) of the
[4CID tasks](https://github.com/mvallet91/4CID_Tasks): a student analyzes a
dataset of tagged sharks for the fictional Oceanic Research Institute.

## Content

| Path | Purpose |
|---|---|
| `materials/Task1.ipynb` | The notebook of the student: the original student version of Task 1, without solutions. |
| `inputs/assignment_descriptions/Task1.txt` | The description of the assignment for the tutor. |
| `inputs/learning_objectives/Task1.txt` | The learning objectives. |
| `inputs/next_steps/Task1.txt` | The options of the `/report` command. |

The dataset `sharks.csv` (about 9 MB) is not in this repository. Download it
from the 4CID tasks repository:

```bash
curl -fsSLO https://raw.githubusercontent.com/mvallet91/4CID_Tasks/main/sharks.csv
```

The notebook is unchanged from the study. Its introduction has the session
logistics of the study (Task 1 and Task 2 in one hour), and option B links to
Task2.ipynb, which is not in the demo. Say this to the audience, or edit the
first cell after the upload.

## Install the demo course

1. Open the teacher settings page. In **Course materials**, upload
   `materials/Task1.ipynb` and `sharks.csv`. The two files must be in the
   same folder.
2. Select `Task1.ipynb` as the notebook that opens after login.
3. Copy the three files in `inputs/` to the same folders in
   `jupyterhub-docker/middleware/inputs/`, or paste their text on the settings
   page (Assignment descriptions, Learning objectives, Next steps, name `Task1`).

## Demonstration script (about 10 minutes)

**Student**

1. Sign up and log in. `Task1.ipynb` opens.
2. In step 1, run the cell with a typing error, for example
   `sharks_df = pd.read_csv('shark.csv')`. The cell fails.
3. Open the chat panel, make the chat `chats/Task1.chat`, and ask: "Why can't it find my file?"
   The tutor gives a hint and does not give the full solution.
4. Ask a question about a concept, for example "What is the difference between
   value_counts and nunique?" This is an `instrumental` message.
5. Ask for a direct answer two or three times, for example "Just give me the code for step 6."
   The tutor classifies these messages as `executive`, and the reactive rules for
   repeated executive requests change the answer.
6. Complete step 6 and type `/report` to get a summary and the next-step options.

**Teacher**

1. Open the teacher dashboard (`/teacher-view`). Select the student. The story shows
   the cell runs, the error and the chat messages.
2. Open the settings page (`/teacher-settings`). In `agent_config.yaml`, change a hint
   in `interventions.reactive.rules` and click **Save**.
3. The student asks one more question. The answer uses the new hint, without a restart.
4. Upload one more file in **Course materials**. It is in the folder of the student
   within one minute.
