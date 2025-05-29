#!/bin/sh

cd $HOME

tgt=$(vespa config get target -c never 2>&1)
if [ "$tgt" != "target = cloud" ]; then
	msg="Configure the CLI: ${tgt}"
	echo "Problem:" "$msg"
	exit 1
fi

app=$(vespa config get application -c never 2>&1)
if [ "$app" = "application = <unset>" ]; then
	msg="Configure the CLI: ${app}"
	echo "Problem:" "$msg"
	exit 1
fi
app=${app#application = }
echo "Found application >>>$app<<<"

auth=$(vespa auth show -c never 2>&1)
case $auth in
    Success:*)
	: ok ;;
    *)
	msg="Need to do: vespa auth login"
	echo "Problem:" "$msg"
	exit 1
	;;
esac

if [ -f .vespa/${app}/data-plane-private-key.pem ]; then
	: ok
else
	echo "Problem: need to run 'vespa auth cert' and deploy"
fi

status=$(vespa status -c never 2>&1)
case $status in
    *Container*ready*mtls*)
	: ok ;;
    *)
	msg="Deploy an application: ${status}"
	echo "Problem:" "$msg"
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

exit 0
