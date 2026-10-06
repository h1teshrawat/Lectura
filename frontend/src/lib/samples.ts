/** Example lectures shown on the home page. Add your own favourites here! */

export interface SampleLecture {
  title: string;
  channel: string;
  url: string;
  videoId: string;
  duration: string;
  tag: string;
}

export const SAMPLE_LECTURES: SampleLecture[] = [
  {
    title: "But what is a neural network?",
    channel: "3Blue1Brown",
    url: "https://www.youtube.com/watch?v=aircAruvnKk",
    videoId: "aircAruvnKk",
    duration: "19 min",
    tag: "Deep learning",
  },
  {
    title: "Backpropagation, intuitively",
    channel: "3Blue1Brown",
    url: "https://www.youtube.com/watch?v=Ilg3gGewQ5U",
    videoId: "Ilg3gGewQ5U",
    duration: "13 min",
    tag: "Deep learning",
  },
  {
    title: "Transformers, the tech behind LLMs",
    channel: "3Blue1Brown",
    url: "https://www.youtube.com/watch?v=wjZofJX0v4M",
    videoId: "wjZofJX0v4M",
    duration: "27 min",
    tag: "GenAI",
  },
];
