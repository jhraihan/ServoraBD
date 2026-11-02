import { lazy, Suspense } from "react";
import { BrowserRouter, useRoutes } from "react-router-dom";

import Layout, { RequireRole } from "./components/Layout";
import { Button, EmptyState, PageLoader } from "./components/ui";
import { ROLE } from "./constants/domain";
import { useDocumentTitle } from "./hooks/useDocumentTitle";
import Home from "./pages/Home";

const Services = lazy(() => import("./pages/Services").then((m) => ({ default: m.Services })));
const CategoryServices = lazy(() => import("./pages/Services").then((m) => ({ default: m.CategoryServices })));
const ProviderSearch = lazy(() => import("./pages/ProviderSearch"));
const ProviderProfile = lazy(() => import("./pages/ProviderProfile"));
const Compare = lazy(() => import("./pages/Compare"));
const Login = lazy(() => import("./pages/Auth").then((m) => ({ default: m.Login })));
const Register = lazy(() => import("./pages/Auth").then((m) => ({ default: m.Register })));
const RequestService = lazy(() => import("./pages/RequestService"));
const MyRequests = lazy(() => import("./pages/Bookings").then((m) => ({ default: m.MyRequests })));
const BookingList = lazy(() => import("./pages/Bookings").then((m) => ({ default: m.BookingList })));
const BookingDetail = lazy(() => import("./pages/Bookings").then((m) => ({ default: m.BookingDetail })));
const ReviewBooking = lazy(() => import("./pages/ReviewBooking"));
const Dashboard = lazy(() => import("./pages/provider/Dashboard"));
const Earnings = lazy(() => import("./pages/provider/Earnings"));
const ProfileSetup = lazy(() => import("./pages/provider/ProfileSetup"));
const TrustPage = lazy(() => import("./pages/provider/TrustPage"));

function page(element) {
  return <Suspense fallback={<PageLoader />}>{element}</Suspense>;
}

function customer(element) {
  return page(<RequireRole role={ROLE.CUSTOMER}>{element}</RequireRole>);
}

function provider(element) {
  return page(<RequireRole role={ROLE.PROVIDER}>{element}</RequireRole>);
}

function NotFound() {
  useDocumentTitle("Page not found");
  return (
    <EmptyState
      title="Page not found"
      body="That page does not exist or has moved."
      action={
        <>
          <Button to="/">Go home</Button>
          <Button variant="secondary" to="/services">Browse services</Button>
        </>
      }
    />
  );
}

const routes = [
  {
    element: <Layout />,
    children: [
      { path: "/", element: <Home /> },
      { path: "/services", element: page(<Services />) },
      { path: "/services/:categorySlug", element: page(<CategoryServices />) },
      { path: "/providers", element: page(<ProviderSearch />) },
      { path: "/providers/:id", element: page(<ProviderProfile />) },
      { path: "/compare", element: page(<Compare />) },
      { path: "/login", element: page(<Login />) },
      { path: "/register", element: page(<Register />) },
      { path: "/request-service", element: customer(<RequestService />) },
      { path: "/my-requests", element: customer(<MyRequests />) },
      { path: "/my-bookings", element: customer(<BookingList basePath="/my-bookings" title="My bookings" subtitle="Jobs a provider has accepted." />) },
      { path: "/my-bookings/:id", element: customer(<BookingDetail />) },
      { path: "/review/:bookingId", element: customer(<ReviewBooking />) },
      { path: "/provider/dashboard", element: provider(<Dashboard />) },
      { path: "/provider/bookings", element: provider(<BookingList basePath="/provider/bookings" title="Jobs" subtitle="Everything you have accepted." />) },
      { path: "/provider/bookings/:id", element: provider(<BookingDetail />) },
      { path: "/provider/earnings", element: provider(<Earnings />) },
      { path: "/provider/profile", element: provider(<ProfileSetup />) },
      { path: "/provider/trust", element: provider(<TrustPage />) },
      { path: "*", element: <NotFound /> },
    ],
  },
];

function AppRoutes() {
  return useRoutes(routes);
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}
