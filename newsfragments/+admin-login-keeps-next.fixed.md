Someone who opens an admin page while logged out now comes back to that page
after logging in. The admin login URL hands over to the login page with its
`next` parameter, and the login page follows it only when it is safe.
