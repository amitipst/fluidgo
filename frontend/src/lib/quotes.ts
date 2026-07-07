// Daily quote of the day — deterministic per calendar day (same for everyone,
// changes automatically at midnight local time), no backend call needed.

const QUOTES: { text: string; author: string }[] = [
  { text: "Success is the sum of small efforts, repeated day in and day out.", author: "Robert Collier" },
  { text: "The harder the conflict, the more glorious the triumph.", author: "Thomas Paine" },
  { text: "Every sale has five basic obstacles: no need, no money, no hurry, no desire, no trust.", author: "Zig Ziglar" },
  { text: "Your attitude, not your aptitude, will determine your altitude.", author: "Zig Ziglar" },
  { text: "People don't buy for logical reasons. They buy for emotional reasons.", author: "Zig Ziglar" },
  { text: "The best salespeople know that their expertise can help solve their prospects' problems.", author: "Jill Konrath" },
  { text: "Sales are contingent upon the attitude of the salesman, not the attitude of the prospect.", author: "W. Clement Stone" },
  { text: "You don't close a sale, you open a relationship.", author: "Patricia Fripp" },
  { text: "Discipline is choosing between what you want now and what you want most.", author: "Abraham Lincoln" },
  { text: "It's not about having the right opportunities. It's about handling the opportunities right.", author: "Mark Hunter" },
  { text: "Consistency is what transforms average into excellence.", author: "Anonymous" },
  { text: "The way to get started is to quit talking and begin doing.", author: "Walt Disney" },
  { text: "Every no gets you closer to a yes.", author: "Anonymous" },
  { text: "Small daily improvements are the key to staggering long-term results.", author: "Anonymous" },
  { text: "The more you help people get what they want, the more you'll succeed.", author: "Zig Ziglar" },
  { text: "Champions keep playing until they get it right.", author: "Billie Jean King" },
  { text: "Effort only fully releases its reward after a person refuses to quit.", author: "Napoleon Hill" },
  { text: "Motivation gets you going, discipline keeps you growing.", author: "John C. Maxwell" },
  { text: "A goal without a plan is just a wish.", author: "Antoine de Saint-Exupery" },
  { text: "Do the hard jobs first. The easy jobs will take care of themselves.", author: "Dale Carnegie" },
  { text: "You miss 100% of the shots you don't take.", author: "Wayne Gretzky" },
  { text: "Well done is better than well said.", author: "Benjamin Franklin" },
  { text: "The pessimist sees difficulty in every opportunity. The optimist sees opportunity in every difficulty.", author: "Winston Churchill" },
  { text: "Opportunities don't happen. You create them.", author: "Chris Grosser" },
  { text: "The only place where success comes before work is in the dictionary.", author: "Vidal Sassoon" },
  { text: "Push yourself, because no one else is going to do it for you.", author: "Anonymous" },
  { text: "Great things never came from comfort zones.", author: "Anonymous" },
  { text: "Don't watch the clock; do what it does — keep going.", author: "Sam Levenson" },
  { text: "Believe you can and you're halfway there.", author: "Theodore Roosevelt" },
  { text: "The future depends on what you do today.", author: "Mahatma Gandhi" },
];

function dayOfYear(d: Date): number {
  const start = new Date(d.getFullYear(), 0, 0);
  const diff = d.getTime() - start.getTime();
  return Math.floor(diff / 86400000);
}

export function getQuoteOfDay(): { text: string; author: string } {
  const idx = dayOfYear(new Date()) % QUOTES.length;
  return QUOTES[idx];
}
