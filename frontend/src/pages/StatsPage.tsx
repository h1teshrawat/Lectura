import { motion } from "framer-motion";
import { ChartColumn, GraduationCap, Layers, ListChecks, Plus, Table2, Target } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link } from "react-router";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { useStats } from "@/hooks/queries";
import { cn } from "@/lib/cn";
import type { Stats } from "@/types/api";

/*
 * Chart design rules followed here (from our data-viz guidelines):
 * - one axis per chart, thin marks (2px lines, 8px markers, 4px rounded bar ends)
 * - recessive grid and axes; text in text colours, never in series colours
 * - colours from a palette validated for colour-blind separation (--chart-1/2)
 * - a tooltip on every chart, a legend when there are 2+ series, a table view for each chart
 */

const AXIS = { stroke: "var(--chart-axis)", fontSize: 12, tickLine: false, axisLine: false } as const;

function shortDate(iso: string): string {
  return new Date(/[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
  });
}

function dayLabel(isoDay: string): string {
  // "2026-10-06" is a local calendar day: build it in local time, not UTC.
  const [y, m, d] = isoDay.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { weekday: "short", day: "numeric" });
}

export function StatsPage() {
  const { data, isLoading, isError, error } = useStats();

  if (isLoading) return <StatsSkeleton />;
  if (isError || !data) {
    return (
      <div className="mx-auto max-w-md px-4 py-24">
        <EmptyState icon={<ChartColumn className="size-6" />} title="Couldn't load stats" description={error?.message ?? ""} />
      </div>
    );
  }
  if (data.totals.lectures === 0) {
    return (
      <div className="mx-auto max-w-md px-4 py-24">
        <EmptyState
          icon={<ChartColumn className="size-6" />}
          title="No stats yet"
          description="Process a lecture, take a quiz and review some flashcards: your progress will show up here."
          action={<Link to="/"><Button icon={<Plus className="size-4" />}>Add a lecture</Button></Link>}
        />
      </div>
    );
  }

  const { totals } = data;
  const masteredPercent = totals.flashcards_total ? Math.round((100 * totals.flashcards_mastered) / totals.flashcards_total) : 0;

  return (
    <div className="mx-auto max-w-7xl space-y-6 px-4 py-8 sm:px-6 sm:py-10">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Your learning stats</h1>
        <p className="mt-1 text-sm text-muted">Quizzes, flashcards and study activity across all your lectures.</p>
      </div>

      {/* Headline numbers: stat tiles, not charts */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile icon={<GraduationCap className="size-4" />} label="Lectures" value={totals.lectures} />
        <StatTile
          icon={<ListChecks className="size-4" />}
          label="Quizzes taken"
          value={totals.quizzes_taken}
          detail={`${totals.questions_answered} questions answered`}
        />
        <StatTile
          icon={<Target className="size-4" />}
          label="Average score"
          value={totals.average_percent === null ? "–" : `${Math.round(totals.average_percent)}%`}
          detail={totals.best_percent === null ? "Take a quiz to start" : `Best: ${Math.round(totals.best_percent)}%`}
        />
        <StatTile
          icon={<Layers className="size-4" />}
          label="Flashcards mastered"
          value={`${totals.flashcards_mastered}/${totals.flashcards_total}`}
          detail={`${masteredPercent}% · ${totals.cards_reviewed} reviews`}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <ScoreHistoryCard history={data.score_history} />
        <ActivityCard activity={data.activity} />
      </div>
      <div className="grid gap-6 lg:grid-cols-[2fr_3fr]">
        <MasteryCard boxes={data.box_distribution} total={totals.flashcards_total} mastered={totals.flashcards_mastered} />
        <LectureTable lectures={data.lectures} />
      </div>
    </div>
  );
}

// ----------------------------------------------------------------- pieces

function StatTile({ icon, label, value, detail }: { icon: ReactNode; label: string; value: ReactNode; detail?: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl border border-border bg-surface p-4 sm:p-5"
    >
      <p className="flex items-center gap-1.5 text-sm text-muted">
        {icon}
        {label}
      </p>
      <p className="mt-2 text-3xl font-semibold tracking-tight">{value}</p>
      {detail && <p className="mt-1 text-xs text-muted">{detail}</p>}
    </motion.div>
  );
}

/** A card holding a chart, with a toggle to show the same data as a table. */
function ChartCard({ title, subtitle, legend, chart, table, empty }: {
  title: string;
  subtitle: string;
  legend?: ReactNode;
  chart: ReactNode;
  table: ReactNode;
  empty?: string;
}) {
  const [showTable, setShowTable] = useState(false);
  return (
    <section className="rounded-2xl border border-border bg-surface p-4 sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="font-semibold">{title}</h2>
          <p className="text-xs text-muted">{subtitle}</p>
        </div>
        {!empty && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowTable((s) => !s)}
            icon={showTable ? <ChartColumn className="size-4" /> : <Table2 className="size-4" />}
            aria-label={showTable ? "Show chart" : "Show as table"}
          >
            <span className="hidden sm:inline">{showTable ? "Chart" : "Table"}</span>
          </Button>
        )}
      </div>
      {legend && !empty && !showTable && <div className="mt-3 flex flex-wrap gap-4 text-xs text-muted">{legend}</div>}
      <div className="mt-4">
        {empty ? (
          <p className="grid h-56 place-items-center rounded-xl border border-dashed border-border text-sm text-muted">{empty}</p>
        ) : showTable ? (
          <div className="max-h-64 overflow-y-auto">{table}</div>
        ) : (
          <div className="h-56">{chart}</div>
        )}
      </div>
    </section>
  );
}

function LegendItem({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="size-2.5 rounded-sm" style={{ background: color }} aria-hidden />
      {label}
    </span>
  );
}

function TooltipBox({ title, rows }: { title: string; rows: { color?: string; label: string; value: string }[] }) {
  return (
    <div className="rounded-lg border border-border bg-surface px-3 py-2 text-xs shadow-lg">
      <p className="mb-1 font-medium text-fg">{title}</p>
      {rows.map((row) => (
        <p key={row.label} className="flex items-center gap-1.5 text-muted">
          {row.color && <span className="size-2 rounded-sm" style={{ background: row.color }} />}
          {row.label}: <span className="font-medium text-fg tabular-nums">{row.value}</span>
        </p>
      ))}
    </div>
  );
}

const tableClass =
  "w-full text-left text-sm [&_td]:py-1.5 [&_td+td]:pl-4 [&_th]:pb-2 [&_th]:font-medium [&_th]:text-muted [&_th+th]:pl-4 [&_tr]:border-b [&_tr]:border-border";

function ScoreHistoryCard({ history }: { history: Stats["score_history"] }) {
  const points = history.map((p, i) => ({ ...p, n: i + 1 }));
  return (
    <ChartCard
      title="Quiz scores over time"
      subtitle={`Your last ${history.length} quiz${history.length === 1 ? "" : "zes"}, in order`}
      empty={history.length === 0 ? "Take a quiz to see your scores here." : undefined}
      chart={
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
            <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
            <XAxis dataKey="n" {...AXIS} />
            <YAxis domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} unit="%" {...AXIS} />
            <Tooltip
              cursor={{ stroke: "var(--chart-axis)", strokeDasharray: "3 3" }}
              content={({ active, payload }) => {
                const p = active && payload?.[0]?.payload;
                if (!p) return null;
                return (
                  <TooltipBox
                    title={`Quiz ${p.n} · ${shortDate(p.taken_at)}`}
                    rows={[
                      { color: "var(--chart-1)", label: "Score", value: `${p.score}/${p.total} (${Math.round(p.percent)}%)` },
                      { label: "Lecture", value: p.lecture_title.length > 32 ? `${p.lecture_title.slice(0, 32)}…` : p.lecture_title },
                      { label: "Difficulty", value: p.difficulty },
                    ]}
                  />
                );
              }}
            />
            <Line
              type="monotone"
              dataKey="percent"
              stroke="var(--chart-1)"
              strokeWidth={2}
              dot={{ r: 4, fill: "var(--chart-1)", stroke: "var(--surface)", strokeWidth: 2 }}
              activeDot={{ r: 6, stroke: "var(--surface)", strokeWidth: 2 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      }
      table={
        <table className={tableClass}>
          <thead><tr><th>#</th><th>Date</th><th>Lecture</th><th className="text-right">Score</th></tr></thead>
          <tbody>
            {points.map((p) => (
              <tr key={p.attempt_id}>
                <td className="text-muted">{p.n}</td>
                <td>{shortDate(p.taken_at)}</td>
                <td className="max-w-40 truncate">{p.lecture_title}</td>
                <td className="text-right tabular-nums">{Math.round(p.percent)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    />
  );
}

function ActivityCard({ activity }: { activity: Stats["activity"] }) {
  const days = activity.map((d) => ({ ...d, label: dayLabel(d.date) }));
  const hasActivity = activity.some((d) => d.questions_answered || d.cards_reviewed);
  return (
    <ChartCard
      title="Study activity"
      subtitle="Items practised per day, last 14 days"
      empty={hasActivity ? undefined : "No study activity in the last 14 days."}
      legend={
        <>
          <LegendItem color="var(--chart-1)" label="Quiz questions answered" />
          <LegendItem color="var(--chart-2)" label="Flashcards reviewed" />
        </>
      }
      chart={
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={days} margin={{ top: 8, right: 8, bottom: 0, left: -16 }} barCategoryGap="25%">
            <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
            <XAxis dataKey="label" interval="preserveStartEnd" minTickGap={16} {...AXIS} />
            <YAxis allowDecimals={false} {...AXIS} />
            <Tooltip
              cursor={{ fill: "var(--subtle)" }}
              content={({ active, payload }) => {
                const d = active && payload?.[0]?.payload;
                if (!d) return null;
                return (
                  <TooltipBox
                    title={d.label}
                    rows={[
                      { color: "var(--chart-1)", label: "Quiz questions", value: String(d.questions_answered) },
                      { color: "var(--chart-2)", label: "Flashcards", value: String(d.cards_reviewed) },
                    ]}
                  />
                );
              }}
            />
            {/* Stacked segments separated by a 2px gap in the surface colour. */}
            <Bar dataKey="questions_answered" stackId="a" fill="var(--chart-1)" stroke="var(--surface)" strokeWidth={2} isAnimationActive={false} />
            <Bar dataKey="cards_reviewed" stackId="a" fill="var(--chart-2)" stroke="var(--surface)" strokeWidth={2} radius={[4, 4, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      }
      table={
        <table className={tableClass}>
          <thead><tr><th>Day</th><th className="text-right">Quiz questions</th><th className="text-right">Flashcards</th></tr></thead>
          <tbody>
            {[...days].reverse().map((d) => (
              <tr key={d.date}>
                <td>{d.label}</td>
                <td className="text-right tabular-nums">{d.questions_answered}</td>
                <td className="text-right tabular-nums">{d.cards_reviewed}</td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    />
  );
}

function MasteryCard({ boxes, total, mastered }: { boxes: Stats["box_distribution"]; total: number; mastered: number }) {
  return (
    <ChartCard
      title="Flashcard mastery"
      subtitle={`Cards per Leitner box · boxes 4–5 count as mastered (${mastered}/${total})`}
      empty={total === 0 ? "No flashcards yet." : undefined}
      chart={
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={boxes} margin={{ top: 8, right: 8, bottom: 0, left: -16 }} barCategoryGap="30%">
            <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
            <XAxis dataKey="label" {...AXIS} />
            <YAxis allowDecimals={false} {...AXIS} />
            <Tooltip
              cursor={{ fill: "var(--subtle)" }}
              content={({ active, payload }) => {
                const b = active && payload?.[0]?.payload;
                if (!b) return null;
                const hint = b.box === 0 ? "Never reviewed" : b.box >= 4 ? "Mastered" : "Learning";
                return <TooltipBox title={b.label} rows={[{ color: "var(--chart-1)", label: hint, value: `${b.count} cards` }]} />;
              }}
            />
            <Bar dataKey="count" fill="var(--chart-1)" radius={[4, 4, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      }
      table={
        <table className={tableClass}>
          <thead><tr><th>Box</th><th className="text-right">Cards</th></tr></thead>
          <tbody>
            {boxes.map((b) => (
              <tr key={b.box}><td>{b.label}</td><td className="text-right tabular-nums">{b.count}</td></tr>
            ))}
          </tbody>
        </table>
      }
    />
  );
}

function LectureTable({ lectures }: { lectures: Stats["lectures"] }) {
  return (
    <section className="rounded-2xl border border-border bg-surface p-4 sm:p-5">
      <h2 className="font-semibold">By lecture</h2>
      <p className="text-xs text-muted">Quiz results and flashcard progress for each lecture</p>
      <div className="mt-4 overflow-x-auto">
        <table className={cn(tableClass, "min-w-[480px]")}>
          <thead>
            <tr>
              <th>Lecture</th>
              <th className="text-right">Quizzes</th>
              <th className="text-right">Avg</th>
              <th className="text-right">Last</th>
              <th className="w-36 pl-4">Mastered</th>
            </tr>
          </thead>
          <tbody>
            {lectures.map((l) => {
              const pct = l.flashcards_total ? (100 * l.flashcards_mastered) / l.flashcards_total : 0;
              return (
                <tr key={l.lecture_id}>
                  <td className="max-w-56">
                    <Link to={`/lectures/${l.lecture_id}`} className="block truncate font-medium hover:text-accent">
                      {l.title}
                    </Link>
                  </td>
                  <td className="text-right tabular-nums">{l.quizzes}</td>
                  <td className="text-right tabular-nums">{l.average_percent === null ? "–" : `${Math.round(l.average_percent)}%`}</td>
                  <td className="text-right tabular-nums">{l.last_percent === null ? "–" : `${Math.round(l.last_percent)}%`}</td>
                  <td className="pl-4">
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-subtle">
                        <div className="h-full rounded-full bg-[var(--chart-1)]" style={{ width: `${pct}%` }} />
                      </div>
                      <span className="w-12 text-right text-xs text-muted tabular-nums">
                        {l.flashcards_mastered}/{l.flashcards_total}
                      </span>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function StatsSkeleton() {
  return (
    <div className="mx-auto max-w-7xl space-y-6 px-4 py-10 sm:px-6">
      <Skeleton className="h-8 w-64" />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-28 rounded-2xl" />)}
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <Skeleton className="h-80 rounded-2xl" />
        <Skeleton className="h-80 rounded-2xl" />
      </div>
    </div>
  );
}
