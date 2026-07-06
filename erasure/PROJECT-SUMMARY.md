# Erasure, plain summary

## What Erasure is

Erasure is a tool Alex built that helps people get their personal information off the internet. Companies called data brokers collect your name, address, phone number, and more, then sell it to anyone who pays. Erasure finds where your information is showing up and sends requests asking those companies to delete it, using real privacy laws to back up the request.

## What it already does

- Scans the internet to find where your information is listed
- Writes letters to companies demanding they delete your data, using the exact law that gives you the right to ask
- Keeps a checklist so you know which companies you already asked and which ones still owe you a response
- Finds old accounts you forgot about (like a sign up from years ago) and gives you a direct link to delete them
- Has a working website people can use right now: erasure-privacy.vercel.app

## What's stuck right now

California has a special government website where you can ask every company at once to delete your data, instead of asking each one by hand. Erasure is supposed to fill out that form automatically. The tricky part is that website sends you a one time code by text or email that a person has to type in themselves, a computer can't do that part. Nobody has walked through that step yet to see what happens after you type the code in, so that last piece of the tool is unfinished.

## What happens next

Alex needs to sit down, turn on a setting that makes it look like he is browsing from California, and walk through that one time code step himself while the tool watches and records what the screens look like. Once that happens, the last piece can get built and the whole California request can run automatically.
