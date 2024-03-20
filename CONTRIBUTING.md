# Contributing to "Chat with your data" Solution Accelerator

This project welcomes contributions and suggestions.  Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit https://cla.opensource.microsoft.com.

When you submit a pull request, a CLA bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

 - [Code of Conduct](#coc)
 - [Issues and Bugs](#issue)
 - [Feature Requests](#feature)
 - [Submission Guidelines](#submit)

## <a name="coc"></a> Code of Conduct
Help us keep this project open and inclusive. Please read and follow our [Code of Conduct](https://opensource.microsoft.com/codeofconduct/).

## <a name="issue"></a> Found an Issue?
If you find a bug in the source code or a mistake in the documentation, you can help us by
[submitting an issue](#submit-issue) to the GitHub Repository. Even better, you can
[submit a Pull Request](#submit-pr) with a fix.

## <a name="feature"></a> Want a Feature?
You can *request* a new feature by [submitting an issue](#submit-issue) to the GitHub
Repository. If you would like to *implement* a new feature, please submit an issue with
a proposal for your work first, to be sure that we can use it.

* **Small Features** can be crafted and directly [submitted as a Pull Request](#submit-pr).

## Managing Dependencies Using Poetry

Poetry is a package manager for Python that allows developers to manage dependencies, create virtual environments, and package their projects for distribution, all using a single command-line tool.

Poetry is setup for you in the devcontainer, but should you need to set this up manually you can 
```sh
sh ./.devcontainer/postCreate.sh
```

The following manual steps can also be followed to setup poetry:
- Poetry can be installed using `pip install poetry`. 
- Using `poetry init` poetry creates a `pyproject.toml` file with all the main dependencies required to run the application. 
- Executing `poetry install` from the root folder which has the `pyproject.toml` file, installs all the dependencies and creates a virtual environment which is used to run the application. `poetry install` also generates a `poetry.lock` file which locks the dependency versions so that any user who installs the application get the same package version.
- Executing `pip install .` from the root folder only installs the main dependencies.
- Dependencies for different environments (dev, test etc.) can be managed by creating groups in the `pyproject.toml` file.
- Installing dependencies for different groups can be done using `poetry install --with <group_name>`

* Adding new package to [pyproject.toml](#pyproject.toml) :

  To add a new package execute the below command:
  ```shell
  poetry add <package-name>
  ``` 
  To add a package to specific group:
  ``` shell
  poetry add <package-name> --group <group-name>
  ```

  `poetry add <package-name>` updates the `poetry.lock` file.

  **Note**: In case the pyproject.toml file is manually updated, the following command should be executed to update the `poetry.lock` file.

  ``` shell 
  poetry lock --no-update
  ```  
  `--no-update` Locks the packages without updating the locked versions.

## <a name="submit"></a> Submission Guidelines

### <a name="submit-issue"></a> Submitting an Issue
Before you submit an issue, search the archive, maybe your question was already answered.

If your issue appears to be a bug, and hasn't been reported, open a new issue.
Help us to maximize the effort we can spend fixing issues and adding new
features, by not reporting duplicate issues.  Providing the following information will increase the
chances of your issue being dealt with quickly:

* **Overview of the Issue** - if an error is being thrown a non-minified stack trace helps
* **Version** - what version is affected (e.g. 0.1.2)
* **Motivation for or Use Case** - explain what are you trying to do and why the current behavior is a bug for you
* **Browsers and Operating System** - is this a problem with all browsers?
* **Reproduce the Error** - provide a live example or a unambiguous set of steps
* **Related Issues** - has a similar issue been reported before?
* **Suggest a Fix** - if you can't fix the bug yourself, perhaps you can point to what might be
  causing the problem (line of code or commit)

You can file new issues by providing the above information at the corresponding repository's issues link: https://github.com/[organization-name]/[repository-name]/issues/new].

### <a name="submit-pr"></a> Submitting a Pull Request (PR)
Before you submit your Pull Request (PR) consider the following guidelines:

* Search the repository (https://github.com/[organization-name]/[repository-name]/pulls) for an open or closed PR
  that relates to your submission. You don't want to duplicate effort.

* Make your changes in a new git fork:

* Commit your changes using a descriptive commit message
* If you are using the devcontainer, committing code will run black and flake8 to lint python code. You can run `black .` or `flake8 .` at anytime.
* Push your fork to GitHub:
* In GitHub, create a pull request
* If we suggest changes then:
  * Make the required updates.
  * Rebase your fork and force push to your GitHub repository (this will update your Pull Request):

    ```shell
    git rebase master -i
    git push -f
    ```

That's it! Thank you for your contribution!
