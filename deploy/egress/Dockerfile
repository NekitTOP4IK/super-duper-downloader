FROM alpine:3.24

RUN apk add --no-cache iptables ip6tables
COPY rules.sh /rules.sh

CMD ["/rules.sh"]
