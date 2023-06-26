from OpenSSL import crypto

def generate_certificate()->bool:
    """
    Generates a self-signed SSL certificate and private key and saves them to files.

    Returns:
    bool: True if the certificate was generated successfully, False otherwise.
    """
    # Generate a private key
    private_key = crypto.PKey()
    private_key.generate_key(crypto.TYPE_RSA, 2048)

    # Create a self-signed cert
    cert = crypto.X509()
    cert.get_subject().CN = 'localhost'
    cert.set_serial_number(1)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(31536000)  # Valid for a year
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(private_key)
    cert.sign(private_key, 'sha256')

    # Write private key and certificate to files
    with open('key.pem', 'wt') as f:
        f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, private_key).decode('utf-8'))

    with open('cert.pem', 'wt') as f:
        f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert).decode('utf-8'))
    
    print("Certificate generated.")
    return True

if __name__ == "__main__":
    generate_certificate()