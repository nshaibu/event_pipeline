## SSL Certificate Generator

This script provides:

1. **Generate private keys** with customizable key sizes
2. **Create Certificate Signing Requests (CSRs)** for getting certificates from a Certificate Authority
3. **Generate self-signed certificates** for development or internal use
4. **Sign CSRs with your own CA** to create certificate chains
5. **Command-line interface** with various arguments and subcommands
6. **Output to a dedicated certificates directory**

### How to Use the Script

1. **Create a private key**:
```bash
python ssl_certificate_generator.py create-key --key-file server.key

OR

python ssl_certificate_generator.py create-key --key-file ca.key --key-size 4096
```

2. **Create a CSR**:
```
python ssl_certificate_generator.py create-csr --key-file server.key --csr-file server.csr --common-name example.com --organization "My Company"
```

3. **Create a self-signed certificate**:
```
python ssl_certificate_generator.py create-self-signed --key-file server.key --cert-file server.crt --common-name example.com --days 365
```

4. **Sign a CSR with your CA**:
```
python ssl_certificate_generator.py sign-csr --ca-key ca.key --ca-cert ca.crt --csr-file server.csr --cert-file server.crt
```



The script assumes `OpenSSL` installed.