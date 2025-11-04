echo -n "Creating .env file with Vespa endpoint and certificate paths..."

app=$(vespa config get application -c never 2>&1)
if [ "$app" = "application = <unset>" ]; then
        msg="Configure the CLI: vespa config set application <tenant>.<application>"
        echo "$msg"
        exit 1
fi
app=${app#application = }

if [ -f $HOME/.vespa/${app}/data-plane-private-key.pem ]; then
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

# create a .env file from env.example
cp env.example .env

# replace the placeholders in the .env file
sed -i "s|<mTLS_ENDPOINT_DNS_GOES_HERE>|$ENDPOINT_DNS|" .env
sed -i "s|<YOUR_TENANT>.<YOUR_APPLICATION>.default|$app|" .env

echo "done"

echo
echo "Creating virtual environment and installing requirements..."
python3 -m venv judgements_venv
source judgements_venv/bin/activate
pip install -r requirements.txt