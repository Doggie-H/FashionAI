import AdminReviewDashboard from '../../components/AdminReviewDashboard';

export const metadata = {
  title: 'Admin Outbox Review | AI Stylist',
  description: 'Review durable outbox dead-letter events and authorize controlled replay.',
};

export default function AdminOutboxPage() {
  return <AdminReviewDashboard />;
}
