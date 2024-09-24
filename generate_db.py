import sys
import os
import subprocess
import pathlib
import logging

from db_generation import git_database, git_log_format

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


def generate_db(log_output, database_path):
    """
    Generates the SQLite database by processing Git log output.

    Args:
        log_output (file-like object): The stdout from the Git log subprocess.
        database_path (str): Path where the SQLite database will be created.

    Returns:
        str: The hash of the last processed commit.
    """
    try:
        con = git_database.db_connection(database_path)
        cur = con.cursor()

        git_database.create_tables(cur)

        lines = []

        while True:
            line = git_database.get_next_line(log_output)
            if not line:
                break
            if chr(line[0]) == git_database.COMMIT_START_SYMBOL:
                last_commit = git_database.handle_commit(cur, lines)
                lines = [line]
            else:
                lines.append(line)
        # Handle the last commit if any
        if lines:
            last_commit = git_database.handle_commit(cur, lines)

        git_database.create_indices(cur)

        con.commit()
        con.close()

        return last_commit
    except Exception as e:
        logging.error(f"An error occurred during database generation: {e}")
        sys.exit(1)


def get_submodules(source_path):
    """
    Retrieves submodule paths from the given Git repository.

    Args:
        source_path (Path): Path to the Git repository.

    Returns:
        list of Path: List of submodule paths.
    """
    try:
        git_command = [
            "git",
            "-C",
            str(source_path),
            "config",
            "--file",
            ".gitmodules",
            "--get-regexp",
            r"submodule\..*\.path"
        ]
        logging.debug(f"Running Git command: {' '.join(git_command)}")
        process = subprocess.Popen(git_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()

        if process.returncode != 0:
            stderr_decoded = stderr.decode().strip()
            if "No such file or directory" in stderr_decoded:
                logging.info(f"No .gitmodules file found in {source_path}.")
                return []
            else:
                logging.error(f"Git command failed with return code {process.returncode}: {stderr_decoded}")
                return []

        submodule_paths = []
        for line in stdout.decode().splitlines():
            key, path = line.split()
            submodule_paths.append(path.strip())

        logging.debug(f"Found submodules: {submodule_paths}")
        return [source_path / pathlib.Path(path) for path in submodule_paths]
    except FileNotFoundError:
        logging.error("Git is not installed or not found in the system's PATH.")
        sys.exit(1)
    except Exception as e:
        logging.error(f"An error occurred while retrieving submodules: {e}")
        return []


def generate_recursive(source_path, source_path_parent, dest_dir_parent):
    """
    Recursively generates databases for the repository and its submodules.

    Args:
        source_path (Path): Path to the current repository.
        source_path_parent (Path): Path to the parent repository.
        dest_dir_parent (Path): Directory where databases are stored.
    """
    try:
        logging.info(f"Processing repository at {source_path}")
        repo_name = source_path.stem

        # Determine the destination directory
        dest_dir = dest_dir_parent / source_path.relative_to(source_path_parent)

        # Create the destination directory if it doesn't exist
        dest_dir.mkdir(parents=True, exist_ok=True)
        database_path = (dest_dir / repo_name).with_suffix(".db")

        # Determine the path for the last commit file
        last_commit_file = dest_dir / "lastcommit.txt"
        if last_commit_file.is_file():
            with open(last_commit_file, "r") as f:
                last_commit = f.read().strip()
            logging.debug(f"Last commit for {repo_name}: {last_commit}")
        else:
            last_commit = None
            logging.debug(f"No previous commit found for {repo_name}.")

        # Get the Git log subprocess
        log_process = git_log_format.get_log_process(source_path, last_commit)

        log_output = log_process.stdout

        # Generate the database
        last_commit = generate_db(log_output, database_path)

        # Update the last commit file
        if last_commit:
            with open(last_commit_file, "w") as f:
                f.write(last_commit)
            logging.debug(f"Updated last commit for {repo_name}: {last_commit}")

        logging.info(f"Database generated at \"{database_path.absolute()}\"")

        # Retrieve submodule paths
        submodule_paths = get_submodules(source_path)
        for submodule_path in submodule_paths:
            if not submodule_path.is_dir():
                logging.warning(f"Submodule path does not exist: {submodule_path}")
                continue
            generate_recursive(submodule_path, source_path, dest_dir)

        # Write the .gitmodules file in the destination directory
        submodules_file = dest_dir / ".gitmodules"
        if submodule_paths:
            with open(submodules_file, "w") as f:
                for path in submodule_paths:
                    f.write(f"{path.relative_to(source_path)}\n")
            logging.debug(f"Wrote .gitmodules for {repo_name} with submodules: {submodule_paths}")
        else:
            logging.debug(f"No submodules to write for {repo_name}.")

    except Exception as e:
        logging.error(f"An error occurred while processing {source_path}: {e}")


def main():
    """
    Main function to initiate the database generation process.
    """
    if len(sys.argv) < 2:
        print("Usage: python generate_db.py <path_to_repo_dir>")
        sys.exit(1)

    repo_dir = pathlib.Path(sys.argv[1]).resolve()

    if not repo_dir.is_dir():
        logging.error(f"The provided path '{repo_dir}' is not a directory.")
        sys.exit(1)

    # Define the directory where databases will be stored
    # Use the current working directory instead of repo_dir
    current_dir = pathlib.Path.cwd()
    repos_dir = current_dir / "repos"
    repos_dir.mkdir(exist_ok=True)

    generate_recursive(repo_dir, repo_dir.parent, repos_dir)


if __name__ == "__main__":
    main()
