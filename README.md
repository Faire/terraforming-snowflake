# :snowflake: Terraforming Snowflake
## Overview
What the code does: Before running anything you'll notice the `snowflake` folder only has `main.tf`. Running the `terraformer` python script will:
1. Generate new `.tf` files in the `snowflake` folder
2. Generate all the `terraform import` statements to build the tfstate, appending them to `terraformer/tf_snowflake_import_resources.sh`

DISCLAIMER: **_All_** of the generated files (`*.tf` files and `tf_snowflake_import_resources.sh`) are built in "append" mode. If you rerun the script, it will re-append to the same files, causing duplicates. This was an intentional choice, as duplicates were safer than overwriting.

## 1. :flashlight: Scraper
### Pre-requisite Steps:
1. Clone this repo to your local machine

2. set up your python environment. Instructions below using `pyenv` and `pyenv-virtualenv` 
    * run `pyenv virtualenv 3.9.11 tf-sf`
	* run `pyenv activate tf-sf && pip install -r terraformer/requirements.txt` 

3. Customize the snowflake client (edit [client.py](https://github.com/Faire/terraforming-snowflake/blob/main/terraformer/client.py#L17-L22) to your own values)
    * note that `ACCOUNT` is actually your "Account Locator". See [Snowflake's examples](https://docs.snowflake.com/en/user-guide/admin-account-identifier.html#non-vps-account-locator-formats-by-cloud-platform-and-region) for reference to correctly enter your account locator. If you have the legacy Snowflake web UI open, the account locator is in the URL: `https://{account_locator}.snowflakecomputing.com`
    * Add query tags that would be useful to track
    
4. Have a Snowflake account you can do Username / Password auth with. 

5. Make sure you've properly set the environment variables `SNOWFLAKE_USER` and `SNOWFLAKE_PASSWORD` with the account information mentioned in the previous step
    
6. Optional step, navigate to the root of the repository and run `make setup-pre-commit` to set up pre-commit hooks for autoformatting your terraform code

### Steps
1. Run the command `python terraformer/terraformer.py` from the repo root
2. Watch everything populate in the `snowflake` folder! (and the `generated_tf_snowflake_import_resources.sh` file in the repo root)
    * You may run into errors if you don't have access to something in Snowflake. Either add it to the exclusion list in `terraformer.py`, or get elevated permissions so you can access it.
    * You'll want to delete all the `generated_*` files between each python run. The script won't delete anything (appends only) to ensure you don't lose any of your own work, but it also means that it creates duplicates.


## 2. :hammer: Building your `tfstate`
### Pre-requisite Steps
1. Make sure you have Terraform installed. We recommend using `tfenv`. On MacOS you can run `brew install tfenv; tfenv install 1.2.5`
2. For your local development, make sure the environment variables `SNOWFLAKE_USER` and `SNOWFLAKE_PASSWORD` are still set in your terminal.
3. Modify [params-default.json](https://github.com/Faire/terraforming-snowflake/blob/main/snowflake/params-default.json#L4-L6) make sure you change this config to match your Snowflake instance.
   * You will probably want to use `snowflake_default_role=SYSADMIN` in production, but for your sandbox tests you should set this to something with less privileges
4. In your terminal, navigate into the `snowflake` folder in the repo and run `terraform init`. Note that if you have an M1 processor you may run into some issues. Check out the appendix at the bottom of this README.

### Steps
1. (Optional, strongly recommended) Before running any import statements, you may want to modularize a bit, adding some `for_each` loops or some sub-modules.

    * This may include renaming some number of pre-existing resources in your Snowflake instance, so they "terra-conform" (groan)
    * Introducing `for_each` means you'll also need to modify the associated `terraform import` statement a little. Don't be afraid to experiment! I threw away tfstates and re-scraped / regenerated it more times than I could keep track.

2. Remove Duplicates
   * If you've run the python script more than once, you have duplicates. It's designed as "append-only" so it doesn't accidentally remove something you've been working on. 
   * Remove duplicates from your terraform code & from your import statements. 
   * If you don't have any custom code, just delete all the `generated_*` files and rerun the python script once. 

3. Run the import statements and generate a tfstate!
   * Make sure your terminal working directory is the `snowflake` directory
   * Test out one `import` command to make sure it works, e.g. `terraform import 'snowflake_database.demo_db' "DEMO_DB"` (use something that actually exists in your Snowflake instance, this is an example)
   * Assuming it works, you can run the whole import script with a command like `bash ../my_import_statements.sh`

4. You probably thought you were ready, but something isn't quite right and you need to iterate. 

    * `terraform state rm someresource` is nice for removing just 1 thing you want to modify, then re-import
    * It may help to start over, rescrape and regenerate tfstate from scratch. This was structured to be easy to iterate on!

5. You can see how you're doing by running a quick `terraform plan`, you'll see how it uses the tfstate you built! Use `plan`s to fix all the discrepancies. 

    * **Don't run `terraform apply` at this stage, you will very likely destroy things you don't want to destroy**

6. (VERY OPTIONAL) You may want to scrap your draft tfstate and start fresh. In that case, you can create a `scrapped_tfstates` directory, and drop your your local `terraform.tfstate` file (and the backups) into it, where terraform doesn't know where to find it. Terraform will assume one doesn't exist, so you can build a new one from scratch 

## 3. :shipit: Setting up Terraform
1. Create Snowflake account that Terraform can use 

2. You'll want a secure S3 bucket / GCP bucket / Blob that not many people have access to besides the admins

    * tfstates contain secrets (snowflake password for the account mentioned in step 1) which _must_ be stored securely
    
3. Have a database you can use for locks, similar access policies as the remote storage above

4. ideally have a Pull Request bot which actually does the `apply`ing for you in your PRs once they've been approved / meet your merge criteria

5. Make sure to configure `main.tf` and `params-default.json` accordingly, so Terraform knows where to look for tfstate / locks

# :notebook_with_decorative_cover: Appendix
## Troubleshooting in Terraform
| Error Message      | Description |
| ----------- | ----------- |
| `Error: Duplicate resource "snowflake_file_format" configuration` | Your terraform `.tf` code has duplicate resources. Find and remove the duplicates |
| `Error: Duplicate resource "snowflake_database" configuration` | Your terraform `.tf` code has duplicate resources. Find and remove the duplicates |
| `Error: Duplicate resource "snowflake_schema" configuration` | Your terraform `.tf` code has duplicate resources. Find and remove the duplicates |
| `Error: Duplicate resource "snowflake_warehouse" configuration` | Your terraform `.tf` code has duplicate resources. Find and remove the duplicates |
| `Error: Duplicate resource "snowflake_role" configuration` | Your terraform `.tf` code has duplicate resources. Find and remove the duplicates |
| `Error: Duplicate resource "snowflake_pipe" configuration` | Your terraform `.tf` code has duplicate resources. Find and remove the duplicates |

## Troubleshooting in Python
| Error Message      | Description |
| ----------- | ----------- |
| `SQL compilation error: Database 'YOUR_SUPER_SECURE_DB' does not exist or not authorized.` | Your current Snowflake user does not have access to see everything. If you want to terraform it, you need higher access privileges. |

## Installing the provider on an M1
Terraform provider installation on M1 macs was inconvenient -- there was no compiled binary for Darwin/arm64 (Apple M1), how to install it:

```bash
mkdir -p ~/development
cd ~/development
git clone git@github.com:Faire/terraforming-snowflake.git
cd terraforming-snowflake/snowflake

brew uninstall m1-terraform-provider-helper
brew install m1-terraform-provider-helper
m1-terraform-provider-helper install snowflake-labs/snowflake -v "v0.43.0"

terraform init

# snowflake-labs/snowflake version 0.43.0 should be available for use in terraform now
# If you want to install a different version, try using m1-terraform-provider-helper 
# to install the different version
```
