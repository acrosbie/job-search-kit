# Getting started with the job search kit

The kit helps you find jobs and decide which ones are worth applying to, by talking to Claude. It reads company job boards for you, screens each posting against what you've told it, and keeps track of what you apply to. Everything about you stays in one folder on your computer.

It takes about 10 minutes to install. Setup is then one conversation of about an hour, one question at a time, and you can stop and pick it up later. You won't need to type a command or open a file.

## What you need

- A computer running **Windows or macOS**.
- A **paid Claude plan** (Pro or Max). On a work account (Team or Enterprise), your administrator may need to allow network access for you.
- Your **resume**, as a PDF or Word file.
- Your **LinkedIn profile** as a PDF: on your LinkedIn profile page, click **More**, then **Save to PDF**.

## 1. Install the Claude app

Go to **claude.com/download**, download the app for your computer, open it, and sign in.

## 2. Add the kit

1. In the left sidebar, click **Customize**, then **Plugins**.
2. Click **+** next to "Personal plugins", then **Add marketplace**, then **Add from a repository**.
3. Type `acrosbie/job-search-kit` and add it.
4. Find **job-search** in the list and click **Install**.

## 3. Make your folder

Make a new, empty folder called **Job Search**, for example in your Documents folder. Everything the kit knows about your search will live there.

## 4. Start setup

1. Look at the top left of the Claude app. Make sure the **speech bubble** icon is selected, not the `</>` icon (that's a different mode, for programmers).
2. Start a **new conversation**.
3. Connect your **Job Search** folder, using the folder option next to the message box. Allow Claude to read and change files there.
4. Type **set me up** and send it.

Claude takes it from there, one question at a time. You can say "not sure" to anything, and you can stop and come back later: it remembers where you got to.

## After setup

Open a conversation with your Job Search folder connected, and say what you want:

- **"Any new jobs?"** checks the job boards.
- **"Go through the new ones"** sorts them into worth applying, your call, and not a fit, with the reason for each.
- **"Apply to the first one, skip the second, it's too far"** records your decisions.
- **Paste a job link** from LinkedIn or anywhere to have it screened too.

If you set up a daily check, it runs while your computer is on and the Claude app is open.

## If something goes wrong

- **"I can't reach job boards"**: Claude needs network access. In the Claude app, open **Settings**, then **Capabilities**, and turn on network access. On a work account your administrator may have to.
- **Claude talks about code or files you don't recognise**: you're in the `</>` view. Switch to the speech bubble and start a new conversation.
- **The kit doesn't seem to know a recent fix**: plugin updates arrive a few minutes after they're released. In **Customize**, then **Plugins**, check the version.
- **Anything else**: [open an issue](https://github.com/acrosbie/job-search-kit/issues), saying what you said and what happened. Never paste your resume or personal details there.

## Your privacy

- What you share with Claude is processed by Anthropic under your plan's terms.
- The kit keeps your files in your folder, and stores page clicks in your own Claude account until they're copied into the folder.
- It sends nothing anywhere else except requests to the public job boards it reads.
- It never applies, messages or emails on your behalf.
