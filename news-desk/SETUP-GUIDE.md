# V6 & Velugu News Desk: setup guide

This puts your live news dashboard online. It takes about 20–30 minutes, once.
No coding is needed: you will only click, drag files and paste text.

When you're done, you'll have a link like `https://your-name.github.io/news-desk/`
that updates itself every 15 minutes, forever, without anyone touching it.

**What you need:** a computer with Chrome or Edge, an email address, and the
`news-desk` folder from the zip file (unzip it first).

---

## Step 1: Create a free GitHub account

1. Go to **github.com** and click **Sign up**.
2. Use an office email if you can (for example, digital@v6news.tv), so the
   account belongs to the organisation, not one person.
3. Pick the **Free** plan.

## Step 2: Create a place for the dashboard (a "repository")

1. After signing in, click the **+** at the top right, then **New repository**.
2. Repository name: `news-desk`
3. Choose **Public**. (The free plan only puts public repositories online.
   The page only shows public news headlines, so nothing private is exposed.)
4. Tick **Add a README file**.
5. Click **Create repository**.

## Step 3: Upload the files

1. On your new repository page, click **Add file → Upload files**.
2. Open the unzipped `news-desk` folder on your computer. Drag these four
   items into the browser window together:
   - the `docs` folder
   - the `scripts` folder
   - `feeds.yaml`
   - `requirements.txt`
3. Wait until all files show in the list, then click **Commit changes**
   (the green button at the bottom).

## Step 4: Add the "every 15 minutes" timer

This file sits in a hidden folder, so it's easier to create it by pasting.

1. Click **Add file → Create new file**.
2. In the name box, type exactly: `.github/workflows/update.yml`
   (GitHub turns each `/` into a folder as you type. That's expected.)
3. On your computer, open `update.yml` from the zip with Notepad
   (Windows) or TextEdit (Mac). Select all, copy, and paste it into the big
   box on GitHub.
4. Click **Commit changes**, then **Commit changes** again in the pop-up.

## Step 5: Let the timer save news

1. Click **Settings** (top of the repository page).
2. In the left menu: **Actions → General**.
3. Scroll to **Workflow permissions**, choose **Read and write permissions**,
   and click **Save**.

## Step 6: Put the dashboard online

1. Still in **Settings**, click **Pages** in the left menu.
2. Under **Build and deployment → Source**, choose **Deploy from a branch**.
3. Under **Branch**, choose **main**, then the folder **/docs**, and click **Save**.
4. After a minute or two, refresh this page. It will show
   **"Your site is live at …"**. That link is your dashboard. Bookmark it
   and share it with the desk.

## Step 7: Run the first update now

The timer starts on its own, but you don't need to wait:

1. Click the **Actions** tab at the top of the repository.
2. Click **Update news** on the left, then **Run workflow → Run workflow**.
3. After about a minute, a green tick appears. Open your dashboard link:
   the news is there.

From now on it updates by itself every 15 minutes, and the open page picks
up the new news every 5 minutes.

---

## Optional: Telugu headline drafts

The dashboard works without this. With it, every story gets a Telugu
headline draft for the desk to polish.

1. Get an API key from Anthropic's Claude Platform (the developer platform
   for Claude). This is a paid service billed by usage. For this dashboard
   it's usually small, but check current pricing there first.
2. In your repository: **Settings → Secrets and variables → Actions →
   New repository secret**.
3. Name: `ANTHROPIC_API_KEY`. Secret: paste your key. Click **Add secret**.

The key stays private, even though the repository is public. Telugu drafts
appear from the next update. Earlier drafts are reused, so the same
headline isn't paid for twice.

---

## Everyday questions

**How do I add or remove a news source?**
Open `feeds.yaml` in your repository and click the pencil icon to edit. Each
source is three lines (name, section, url). Copy a block to add one, or
delete a block to remove one. Click **Commit changes**. The next update
uses the new list.

**How do I share one section?**
Add the section to the end of the link, for example:
`…/news-desk/#telangana-hyd`, `#business`, `#entertainment`.

**The page says some sources aren't working.**
News sites sometimes change or block their feeds. Click "sources working" at
the top of the dashboard to see which ones. You can remove them from
`feeds.yaml`, or ask Claude for a replacement feed address.

**The page says news hasn't updated for a while.**
Open the **Actions** tab. A red cross means a run failed. Click it to see
why, or click **Run workflow** to try again. GitHub's timer can also run a
few minutes late when it's busy. That's normal.

**Is this "real time"?**
Close to it. Stories appear within about 15–30 minutes of being published.
For second-by-second breaking alerts from social media, newsrooms use paid
services such as Dataminr.

**What does "outlets" mean?**
How many different news sites are carrying the same story. The more outlets,
the more the story is spreading. "Single source" means only one site has it
so far: verify before airing.
