The "Enter Sign-In Code" page again shows its heading, the address the code was
sent to, and a working form action. The shared confirm-code base had lost the
blocks its subclasses fill in, so those overrides rendered nowhere.
