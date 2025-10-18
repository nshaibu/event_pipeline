#!/usr/bin/env python3
"""
SSL Certificate Generator Script

This script uses OpenSSL to generate SSL certificates.
It can create self-signed certificates or certificate signing requests (CSRs).

"""

import os
import subprocess
import argparse
import configparser
from datetime import datetime
from pathlib import Path


class SSLCertificateGenerator:
    def __init__(self, config_path=None):
        """Initialize the SSL Certificate Generator."""
        self.config = self._load_config(config_path) if config_path else None
        self._ensure_output_directory()

    def _load_config(self, config_path):
        """Load configuration from a file."""
        config = configparser.ConfigParser()
        config.read(config_path)
        return config

    def _ensure_output_directory(self):
        """Ensure the output directory exists."""
        output_dir = Path("./certificates")
        output_dir.mkdir(exist_ok=True)
        return output_dir

    def generate_private_key(self, key_file, key_size=2048):
        """Generate a private key."""
        cmd = ["openssl", "genrsa", "-out", key_file, str(key_size)]
        subprocess.run(cmd, check=True)
        print(f"Private key generated: {key_file}")

    def generate_csr(self, key_file, csr_file, subject_details):
        """Generate a Certificate Signing Request (CSR)."""
        subject = self._format_subject(subject_details)
        cmd = [
            "openssl",
            "req",
            "-new",
            "-key",
            key_file,
            "-out",
            csr_file,
            "-subj",
            subject,
        ]
        subprocess.run(cmd, check=True)
        print(f"CSR generated: {csr_file}")

    def generate_self_signed_cert(self, key_file, cert_file, subject_details, days=365):
        """Generate a self-signed certificate."""
        subject = self._format_subject(subject_details)
        cmd = [
            "openssl",
            "req",
            "-new",
            "-x509",
            "-key",
            key_file,
            "-out",
            cert_file,
            "-days",
            str(days),
            "-subj",
            subject,
        ]
        subprocess.run(cmd, check=True)
        print(f"Self-signed certificate generated: {cert_file}")

    def _format_subject(self, subject_details):
        """Format the subject string for OpenSSL command."""
        subject_str = ""
        for key, value in subject_details.items():
            if value:
                subject_str += f"/{key}={value}"
        return subject_str

    def generate_certificate_chain(
        self, ca_key, ca_cert, server_csr, server_cert, days=365
    ):
        """Sign a CSR with a CA certificate to create a certificate chain."""
        cmd = [
            "openssl",
            "x509",
            "-req",
            "-in",
            server_csr,
            "-CA",
            ca_cert,
            "-CAkey",
            ca_key,
            "-CAcreateserial",
            "-out",
            server_cert,
            "-days",
            str(days),
        ]
        subprocess.run(cmd, check=True)
        print(f"Signed certificate generated: {server_cert}")


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate SSL certificates using OpenSSL"
    )

    parser.add_argument("--config", help="Path to configuration file")
    parser.add_argument(
        "--output-dir",
        default="./certificates",
        help="Output directory for certificates",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Create private key command
    key_parser = subparsers.add_parser("create-key", help="Create a private key")
    key_parser.add_argument("--key-file", required=True, help="Output key file")
    key_parser.add_argument(
        "--key-size", type=int, default=2048, help="Key size in bits"
    )

    # Create CSR command
    csr_parser = subparsers.add_parser(
        "create-csr", help="Create a Certificate Signing Request"
    )
    csr_parser.add_argument("--key-file", required=True, help="Private key file")
    csr_parser.add_argument("--csr-file", required=True, help="Output CSR file")
    csr_parser.add_argument("--country", help="Country Name (2 letter code)")
    csr_parser.add_argument("--state", help="State or Province Name")
    csr_parser.add_argument("--locality", help="Locality Name")
    csr_parser.add_argument("--organization", help="Organization Name")
    csr_parser.add_argument("--org-unit", help="Organizational Unit Name")
    csr_parser.add_argument(
        "--common-name", required=True, help="Common Name (e.g. server FQDN)"
    )
    csr_parser.add_argument("--email", help="Email Address")

    # Create self-signed certificate command
    self_signed_parser = subparsers.add_parser(
        "create-self-signed", help="Create a self-signed certificate"
    )
    self_signed_parser.add_argument(
        "--key-file", required=True, help="Private key file"
    )
    self_signed_parser.add_argument(
        "--cert-file", required=True, help="Output certificate file"
    )
    self_signed_parser.add_argument(
        "--days", type=int, default=365, help="Validity period in days"
    )
    self_signed_parser.add_argument("--country", help="Country Name (2 letter code)")
    self_signed_parser.add_argument("--state", help="State or Province Name")
    self_signed_parser.add_argument("--locality", help="Locality Name")
    self_signed_parser.add_argument("--organization", help="Organization Name")
    self_signed_parser.add_argument("--org-unit", help="Organizational Unit Name")
    self_signed_parser.add_argument(
        "--common-name", required=True, help="Common Name (e.g. server FQDN)"
    )
    self_signed_parser.add_argument("--email", help="Email Address")

    # Sign CSR with CA command
    sign_parser = subparsers.add_parser(
        "sign-csr", help="Sign a CSR with a CA certificate"
    )
    sign_parser.add_argument("--ca-key", required=True, help="CA private key file")
    sign_parser.add_argument("--ca-cert", required=True, help="CA certificate file")
    sign_parser.add_argument("--csr-file", required=True, help="CSR file to sign")
    sign_parser.add_argument(
        "--cert-file", required=True, help="Output certificate file"
    )
    sign_parser.add_argument(
        "--days", type=int, default=365, help="Validity period in days"
    )

    return parser.parse_args()


def get_subject_from_args(args):
    """Extract subject details from command line arguments."""
    subject = {}
    if args.country:
        subject["C"] = args.country
    if args.state:
        subject["ST"] = args.state
    if args.locality:
        subject["L"] = args.locality
    if args.organization:
        subject["O"] = args.organization
    if args.org_unit:
        subject["OU"] = args.org_unit
    if args.common_name:
        subject["CN"] = args.common_name
    if args.email:
        subject["emailAddress"] = args.email
    return subject


def main():
    """Main function."""
    args = parse_arguments()

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    # Initialize certificate generator
    cert_gen = SSLCertificateGenerator(args.config)

    if args.command == "create-key":
        key_file = output_dir / args.key_file
        cert_gen.generate_private_key(key_file, args.key_size)

    elif args.command == "create-csr":
        key_file = Path(args.key_file)
        csr_file = output_dir / args.csr_file
        subject = get_subject_from_args(args)
        cert_gen.generate_csr(key_file, csr_file, subject)

    elif args.command == "create-self-signed":
        key_file = Path(args.key_file)
        cert_file = output_dir / args.cert_file
        subject = get_subject_from_args(args)
        cert_gen.generate_self_signed_cert(key_file, cert_file, subject, args.days)

    elif args.command == "sign-csr":
        ca_key = Path(args.ca_key)
        ca_cert = Path(args.ca_cert)
        csr_file = Path(args.csr_file)
        cert_file = output_dir / args.cert_file
        cert_gen.generate_certificate_chain(
            ca_key, ca_cert, csr_file, cert_file, args.days
        )

    else:
        print("Please specify a command. Use --help for more information.")


if __name__ == "__main__":
    main()
