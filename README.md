# :snowflake: Terraforming Snowflake
## Overview
What the code does: Before running anything you'll notice the `snowflake` folder only has `main.tf`. Running the `terraformer` python script will:
1. Generate new `.tf` files in the `snowflake` folder
2. Generate all the `terraform import` statements to build the tfstate, appending them to `terraformer/tf_snowflake_import_resources.sh`

DISCLAIMER: **_All_** of the generated files (`*.tf` files and `tf_snowflake_import_resources.sh`) are built in "append" mode. If you rerun the script, it will re-append to the same files, causing duplicates. This was an intentional choice, as duplicates were safer than overwriting.

## 1. :flashlight: Scraper
### Pre-requisite steps:
1. Clone this repo to your local machine
2. set up your python environment, make sure to `pip install -r terraformer/requirements.txt`
3. Customize the snowflake client (see client.py, be sure to set `WAREHOUSE`)
    a) note that `ACCOUNT` is part of your snowflake URL: `{ACCOUNT}.snowflakecomputing.com`
    b) optionally set `DATABASE`,`SCHEMA`, 
    c) Add query tags that would be useful to track
4. Have a Snowflake account you can use Username / Password auth with, and make sure you've properly set all environment variables
    a) `SNOWFLAKE_USER`
    b) `SNOWFLAKE_PASSWORD`
5. Optional step, navigate to the root of the repository and run `make setup-pre-commit` to set up pre-commit hooks for autoformatting your terraform code

### Steps
1. Run the command `python terraformer.py`
2. Watch everything populate!


## 2. :hammer: Building your `tfstate`
1. Before running any import statements, you may want to modularize a bit, adding some `for_each` loops or some sub-modules.
    a) this may include renaming some number of pre-existing resources in your Snowflake instance, so they "terra-conform" (groan)
    b) introducing `for_each` means you'll also need to modify the associated `terraform import` statement a little. Don't be afraid to experiment! I threw away tfstates and re-scraped / regenerated it more times than I could keep track.
2. Once you're ready, run the import statements and generate a tfstate!
3. You probably thought you were ready, but something isn't quite right and you need to iterate. 
    a) `terraform state rm someresource` is nice for removing just 1 thing you want to modify, then re-import
    b) It may help to start over, rescrape and regenerate tfstate from scratch. This was structured to be easy to iterate on!
4. You can see how you're doing by running a quick `terraform plan`, you'll see how it uses the tfstate you built! Use `plan`s to fix all the discrepancies. 
    * **Don't run `terraform apply` at this stage, you will very likely destroy things**


## 3. :shipit: Setting up Terraform
1. Create Snowflake account that Terraform can use 
2. You'll want a secure S3 bucket / GCP bucket / Blob that not many people have access to besides the admins
    a) tfstates contain secrets (snowflake password for the account mentioned in step 1) which _must_ be stored securely
3. Have a database you can use for locks, similar access policies as the remote storage above
4. ideally have a Pull Request bot which actually does the `apply`ing for you in your PRs once they've been approved / meet your merge criteria
5. Make sure to configure `main.tf` and `params-default.json` accordingly, so Terraform knows where to look for tfstate / locks

# :notebook_with_decorative_cover: Appendix
### Installing the provider on an M1
Terraform provider installation on M1 macs was inconvenient -- there was no compiled binary for Darwin/arm64 (Apple M1), how to install it:
m1-terraform-provider-helper is awesome, but the `m1-terraform-provider-helper install snowflake-labs/snowflake -v "v0.36.0"` didn't work for me, so I compiled it myself and dropped it into Terraform's local cache directory (exactly what m1-terraform-provider-helper normally does, but there seems to be something going on)

```bash
mkdir -p ~/development
cd ~/development
git clone git@github.com:Snowflake-Labs/terraform-provider-snowflake.git
cd terraform-provider-snowflake
git checkout v0.36.0
go build -ldflags "-w -s -X github.com/chanzuckerberg/go-misc/ver.GitSha=d055d4c -X github.com/chanzuckerberg/go-misc/ver.Dirty=false" -o terraform-provider-snowflake .
mkdir -p ~/.terraform.d/plugins/registry.terraform.io/snowflake-labs/snowflake/0.36.0/darwin_arm64/terraform-provider-snowflake_0.36.0_x5
mv terraform-provider-snowflake ~/.terraform.d/plugins/registry.terraform.io/snowflake-labs/snowflake/0.36.0/darwin_arm64/terraform-provider-snowflake_0.36.0_x5
# snowflake-labs/snowflake version 0.36.0 should be available for use in terraform now
# If you want to install a different version, try using m1-terraform-provider-helper 
#  first. If it doesn't work, you can get the gritty details above by paying attention
#  to the commands that `m1-terraform-provider-helper` tries running
```
