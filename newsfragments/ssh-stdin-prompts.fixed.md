`phoxtail db pull`, `db push` and the other server commands read a piped
answer again: the ssh call that checks the server's identity used to
swallow it, so `echo y | phoxtail db push <ip>` aborted at the prompt.
