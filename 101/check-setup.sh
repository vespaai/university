#!/bin/sh

cd $HOME

tgt=$(vespa config get target -c never 2>&1)
if [ "$tgt" != "target = cloud" ]; then
	msg="Configure the CLI to target Vespa Cloud: vespa config set target cloud"
	echo "$msg"
	exit 1
fi

app=$(vespa config get application -c never 2>&1)
if [ "$app" = "application = <unset>" ]; then
	msg="Configure the CLI: vespa config set application <tenant>.<application>"
	echo "$msg"
	exit 1
fi
app=${app#application = }
echo "Found application >>>$app<<<"

auth=$(vespa auth show -c never 2>&1)
case $auth in
    Success:*)
	: ok ;;
    *)
	msg="Not logged in, please run: vespa auth login"
	echo "$msg"
	exit 1
	;;
esac

if [ -f .vespa/${app}/data-plane-private-key.pem ]; then
	: ok
else
	msg="Problem: need to run 'vespa auth cert' and deploy an application"
	echo "$msg"
	exit 1
fi

status=$(vespa status -c never 2>&1)
case $status in
    *Container*is\ ready*mtls*)
	: ok ;;
    *)
	msg="Problem: No ready application (did you run 'vespa deploy --wait 300'?)"
	echo "Output from 'vespa status' is:"
	vespa status
	echo "########################################################"
	echo "$msg"
	echo "########################################################"
	exit 1
	;;
esac

ready=${status% is ready *}
endpoint=${ready#Container * at }
ephost=${endpoint#https://}
ENDPOINT_DNS=${ephost%/}

echo "Found secure endpoint: >>>$ENDPOINT_DNS<<<"

mkdir -p $HOME/.local/share/code-server/User
cd $HOME/.local/share/code-server/User

echo '{
  "security.workspace.trust.enabled": false,
  "vespaSchemaLS": {
    "javaHome": "/usr/lib/jvm/java-21-openjdk-amd64/"
  },
  "rest-client.certificates": {
    "'${ENDPOINT_DNS}'": {
        "key":  "'${HOME}/.vespa/${app}'/data-plane-private-key.pem",
        "cert": "'${HOME}/.vespa/${app}'/data-plane-public-cert.pem"
    }
  }
}' > settings.json.new

if [ -f settings.json ] && diff -q settings.json settings.json.new; then
	: already ok
else
	echo "Fixed secure HTTP settings for code server - restarting it"
	mv settings.json.new settings.json
	sudo service code-server restart
fi

find $HOME/lab -name '*.http' -print0 |
	xargs -0 perl -pi -e "s{<mTLS_ENDPOINT_DNS_GOES_HERE>}{$ENDPOINT_DNS}"

# replace 1970-01-01 in all validation-overrides.xml files in the lab directory
# with the current date + 20 days in YYYY-MM-DD format
find $HOME/lab -name 'validation-overrides.xml' -print0 |
	xargs -0 perl -pi -e "s{1970-01-01}{$(date -d '20 days' +%Y-%m-%d)}"

exit 0
