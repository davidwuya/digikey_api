from authorization import check_token

# before every API call, run check_token() to make sure the token is still valid
check_token()
