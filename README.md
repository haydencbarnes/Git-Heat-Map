# Git-Heat-Map

![Map showing the files in a repository that have the most changes](img/example_image.png)
*Map showing the files in a repository that have the most changes; full SVG image available in repo*

## Overview

**Git-Heat-Map** is a tool designed to visualize the activity within a Git repository. By analyzing commit data, it generates an interactive treemap that highlights files based on the number of changes (lines added or removed). This visualization helps in identifying hotspots in the codebase, understanding contributor activity, and tracking project evolution over time.

## Basic Use Guide

Follow these steps to set up and use **Git-Heat-Map** with your private repository:

1. **Clone the Repository:**

   Ensure you have cloned the repository to your local machine.

   ```bash
   git clone /path/to/your/private/repo.git
   cd repo
   ```

2. **Set Up a Python Virtual Environment:**

   It's recommended to use a virtual environment to manage dependencies.

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Required Modules:**

   Install the necessary Python packages using `pip`.

   ```bash
   pip install -r requirements.txt
   ```

4. **Generate the Database:**

   Process the Git history of your repository to generate the SQLite database.

   ```bash
   python generate_db.py /path/to/your/private/repo/
   ```

   - **Note:** If you encounter issues with submodules or wish to skip them, use the `--skip-submodules` flag:

     ```bash
     python generate_db.py /path/to/your/private/repo/ --skip-submodules
     ```

5. **Run the Web Server:**

   Start the Flask web server to serve the heatmap visualization.

   ```bash
   python app.py
   ```

   - **Alternative:** You can also use Flask's CLI to run the server.

     ```bash
     flask run
     ```

     - To run the server on a specific IP address (e.g., accessible from other machines on your network), use:

       ```bash
       flask run --host=0.0.0.0
       ```

6. **Access the Interface:**

   Open your web browser and navigate to [http://127.0.0.1:5000](http://127.0.0.1:5000) to access the **Git-Heat-Map** interface.

7. **Interact with the Heatmap:**

   - **Select Repository:** Choose the repository you want to visualize from the available list.
   
   - **Apply Filters:** Add filters based on emails, commits, filenames, and date ranges to highlight specific activity.
     - **Browse Buttons:** Use the "Browse" buttons to view and select valid filter values.
     - **Manual Input:** Alternatively, input valid [SQLite LIKE patterns](https://www.sqlite.org/lang_expr.html#:~:text=The%20LIKE%20operator%20does%20a,more%20characters%20in%20the%20string.) directly.
     - **Exclusion:** Clicking on filter entries will exclude results matching those entries.
   
   - **Visualization Settings:**
     - **Highlighting:** By default, highlight hues are determined by file extensions. This can be manually overridden as needed.
     - **Performance Options:** Adjust levels of text rendering and set the minimum size of boxes to optimize performance.
   
   - **Update Visualization:**
     - **Submit Query:** Click to apply filters and update the highlighted files.
     - **Refresh:** Update the highlighting hue and redraw based on the current window size.
     - **Navigation:** Click on directories within the heatmap to zoom in, and use the back button in the sidebar to zoom out.

## Project Structure

The project is divided into two main components:

1. **Git Log → Database**

   - **Functionality:** Processes the entire Git history of a repository using `git log` and stores the data in a structured SQLite database.
   - **Database Tables:**
     - **Files:** Tracks filenames.
     - **Commits:** Stores commit hashes, authors, and committers.
     - **CommitFile:** Associates files with commits, recording lines added and removed.
     - **Author:** Maintains author names and emails.
     - **CommitAuthor:** Links commits to authors, supporting multiple authors per commit.
   - **Purpose:** Enables analysis of file activity and contributor behavior within the repository.

2. **Database → Treemap**

   - **Functionality:** Queries the SQLite database to generate a JSON object representing the file tree structure, then creates an interactive treemap visualization.
   - **JSON Structure:**
     ```json
     {
       "type": "directory",
       "name": "root",
       "aggregate": 0,
       "children": [
         {
           "type": "file",
           "name": "file1.py",
           "data": 150
         },
         {
           "type": "directory",
           "name": "subdir",
           "aggregate": 200,
           "children": [
             // Nested files or directories
           ]
         }
       ]
     }
     ```
   - **Visualization:** The treemap's rectangles represent files and directories, sized according to the number of line changes. Interactive features allow users to zoom in/out and apply filters to highlight specific areas of interest.

## Performance

Performance metrics were obtained on a personal machine and may vary based on hardware and repository size.

### Database Generation

| Repo        | Number of Commits | Git Log Time | Git Log Size | Database Time     | Database Size | **Total Time**   |
|-------------|-------------------|--------------|--------------|-------------------|---------------|-------------------|
| ExampleRepo | 10,000            | 2 minutes    | 30MB         | 25 seconds        | 50MB          | **2.5 minutes**   |

- **Scaling:** Time and database size scale linearly with the number of commits.

### Querying Database and Displaying Treemap

| Repo        | Author Filter      | Drawing Treemap Time | Highlighting Treemap Time |
|-------------|--------------------|----------------------|---------------------------|
| ExampleRepo | user@example.com   | 1.2 seconds          | 2.5 seconds               |

- **Note:** Actual rendering times may vary based on browser performance and visualization complexity.

---

**Note:** Ensure that all paths, repository names, and other placeholders are updated to reflect your actual project details. Additionally, if you are using this tool with a private repository, handle sensitive information appropriately and restrict access as needed.

If you have any further questions or need additional assistance, feel free to reach out!