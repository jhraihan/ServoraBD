import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { bookings, reviews } from "../api/endpoints";
import { StarInput } from "../components/domain";
import { Button, EmptyState, ErrorMessage, Field, PageHeader, PageLoader } from "../components/ui";
import { BOOKING_STATE } from "../constants/domain";
import { toast } from "../store/toast";

const ASPECTS = [
  ["punctuality", "Punctuality"],
  ["quality", "Quality of work"],
  ["professionalism", "Professionalism"],
  ["priceFairness", "Fair price"],
];

export default function ReviewBooking() {
  const { bookingId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    rating: 0, punctuality: 0, quality: 0, professionalism: 0, priceFairness: 0, comment: "",
  });

  const { data: booking, isLoading, error, refetch } = useQuery({
    queryKey: ["booking", bookingId],
    queryFn: () => bookings.detail(bookingId),
  });

  const submit = useMutation({
    mutationFn: () => reviews.create({ bookingId: Number(bookingId), ...form }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["booking", bookingId] });
      toast("Review submitted and sealed.");
      navigate(`/my-bookings/${bookingId}`, { replace: true });
    },
  });

  if (isLoading) return <PageLoader />;
  if (error) return <ErrorMessage error={error} onRetry={refetch} />;

  if (booking.state !== BOOKING_STATE.COMPLETED) {
    return <EmptyState title="This job is not finished yet" body="You can review a booking once it is completed." action={<Button to={`/my-bookings/${bookingId}`}>Back to booking</Button>} />;
  }
  if (booking.reviewSubmitted) {
    return <EmptyState title="You have already reviewed this job" body="Thank you — each booking can be reviewed once." action={<Button to={`/my-bookings/${bookingId}`}>Back to booking</Button>} />;
  }

  function set(key) {
    return (value) => setForm((f) => ({ ...f, [key]: value }));
  }

  return (
    <div className="mx-auto max-w-xl">
      <Link to={`/my-bookings/${bookingId}`} className="text-sm font-semibold text-brand-700">← Back to booking</Link>
      <div className="mt-3">
        <PageHeader title={`Review ${booking.providerName}`} subtitle={booking.service?.name} />
      </div>

      <div className="mb-4 rounded-2xl border border-brand-200 bg-brand-50 p-4 text-sm text-brand-900">
        <p className="font-semibold">Your review is sealed until both sides have rated.</p>
        <p className="mt-1">
          {booking.providerName} cannot see what you wrote until they have rated you too, or 14 days pass. They cannot
          make a good review a condition of anything.
        </p>
      </div>

      <form
        className="card space-y-5 p-5 sm:p-6"
        onSubmit={(e) => {
          e.preventDefault();
          submit.mutate();
        }}
      >
        <StarInput name="overall" label="Overall" value={form.rating} onChange={set("rating")} />
        <div className="grid gap-4 sm:grid-cols-2">
          {ASPECTS.map(([key, label]) => (
            <StarInput key={key} name={key} label={`${label} (optional)`} value={form[key]} onChange={set(key)} />
          ))}
        </div>
        <Field label="Comment (optional)" htmlFor="review-comment" hint="Describe the work, not the person. You can edit for 24 hours.">
          <textarea id="review-comment" className="input" rows={4} maxLength={2000} value={form.comment} onChange={(e) => setForm((f) => ({ ...f, comment: e.target.value }))} />
        </Field>
        <ErrorMessage error={submit.error} />
        {!form.rating && <p className="text-sm text-slate-600">Choose an overall rating to submit.</p>}
        <Button type="submit" size="lg" className="w-full" loading={submit.isPending} disabled={!form.rating}>
          Submit review
        </Button>
      </form>
    </div>
  );
}
