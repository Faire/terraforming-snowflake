resource "snowflake_database" "this_is_a_test" {
  name        = "this_is_a_test"
  description = "you can delete this, it's just an example"
  // if no provider is specified, default is used. See main.tf for default
  provider = snowflake.security_admin
}
