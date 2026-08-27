import ReviewerQueueDashboard from '../../components/ReviewerQueueDashboard';

export const metadata = {
  title: 'Reviewer Queue | 3D AI Stylist',
  description: 'Role-scoped review queue with atomic claims and durable audit evidence.',
};

export default function ReviewPage() {
  return <ReviewerQueueDashboard />;
}
