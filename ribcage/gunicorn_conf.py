wsgi_app = "ribcage.wsgi"
# Plain HTTP on 8000, the port the host's proxy forwards to; the container publishes none on the host (#31, #43).
bind = "0.0.0.0:8000"
# A few sync workers, each serving one request at a time (#14).
workers = 3
# Preload fails startup once, before listening, on a bad env (#51).
preload_app = True
control_socket_disable = True
# The log keeps time, request line, status and duration only: no client address, so never X-Forwarded-For (#31).
accesslog = "-"
access_log_format = '%(t)s "%(r)s" %(s)s %(M)sms'
