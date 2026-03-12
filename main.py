import smtplib
from email.message import EmailMessage

# Configuration
EMAIL_ADDRESS = "no.reply.hackfox@gmail.com"
EMAIL_PASSWORD = "pwlz mebo sbua hjaz" # Ton mot de passe d'application

msg = EmailMessage()
msg['Subject'] = "Test Python"
msg['From'] = EMAIL_ADDRESS
msg['To'] = "maindron.kelian@laposte.net"
msg.set_content("Salut ! Ceci est un mail envoyé via Python.")

try:
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)
    print("Email envoyé avec succès !")
except Exception as e:
    print(f"Erreur : {e}")