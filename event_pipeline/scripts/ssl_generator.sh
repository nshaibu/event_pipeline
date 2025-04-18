#!/usr/bin/env bash

private_key_file=client.key
csr_key_file=client.csr
crt_key_file=client.crt
ca_key_file=client_ca.crt
organization="Example Company"
comman_name="example.com"


python3 ./ssl_certificate_generator.py create-key --key-file client.key

python3 ./ssl_certificate_generator.py create-csr --key-file ./certificates/client.key --csr-file client.csr --common-name  --organization "My Company"

python3 ./ssl_certificate_generator.py create-self-signed --key-file ./certificates/client.key --cert-file client.crt --common-name example.com --days 365

python3 ./ssl_certificate_generator.py sign-csr --ca-key ./certificates/client.key --ca-cert ./certificates/client.crt --csr-file ./certificates/client.csr --cert-file client_ca.crt