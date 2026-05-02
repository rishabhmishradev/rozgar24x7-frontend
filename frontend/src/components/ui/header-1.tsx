'use client';

import React from 'react';
import { Button, buttonVariants } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { MenuToggleIcon } from '@/components/ui/menu-toggle-icon';
import { useScroll } from '@/components/ui/use-scroll';
import { createPortal } from 'react-dom';
import { Link } from "react-router-dom";
import { useAuth } from '@/lib/auth-context';
import { SignInModal } from '@/components/auth/SignInModal';
import { LogOut, LayoutDashboard, FileText, BarChart2, ChevronDown } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { useLocation } from "react-router-dom";

export function Header() {
	const [open, setOpen] = React.useState(false);
	const [profileOpen, setProfileOpen] = React.useState(false);
	const scrolled = useScroll(10);
	const { user, signOut, openModal } = useAuth();
	const profileRef = React.useRef<HTMLDivElement>(null);
	const pathname = useLocation().pathname;

	const links = [
		{ label: 'Features', href: '/#features' },
		{ label: 'Pricing', href: '/pricing' },
		{ label: 'ATS Checker', href: '/ats-analysis' },
	];

	React.useEffect(() => {
		if (open) {
			document.body.style.overflow = 'hidden';
		} else {
			document.body.style.overflow = '';
		}
		return () => {
			document.body.style.overflow = '';
		};
	}, [open]);

	React.useEffect(() => {
		const handler = (e: MouseEvent) => {
			if (profileRef.current && !profileRef.current.contains(e.target as Node)) {
				setProfileOpen(false);
			}
		};
		document.addEventListener("mousedown", handler);
		return () => document.removeEventListener("mousedown", handler);
	}, []);

	return (
		<>
			<SignInModal />
			<header
				className={cn('sticky top-0 z-50 w-full border-b border-transparent', {
					'bg-background/95 supports-[backdrop-filter]:bg-background/50 border-border backdrop-blur-lg':
						scrolled,
				})}
			>
				<nav className="flex h-14 lg:h-16 w-full items-center px-4 sm:px-8 lg:px-12">
					<div className="flex items-center flex-1">
						{/* Logo */}
						<Link to="/" className="flex items-center gap-2 group mr-2 sm:mr-6 lg:mr-10 max-w-[160px] sm:max-w-none">
							<div className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-lg shadow-md group-hover:scale-105 transition-transform">
								<img src="/assets/logo.PNG" alt="Rozgar 24x7 logo" className="h-full w-full object-contain" />
							</div>
							<span className="font-semibold text-2xl tracking-tight hidden sm:block text-zinc-900 dark:text-zinc-50">
								ROZGAR <span className="font-semibold text-teal-600">24X7</span>
							</span>
						</Link>

						{/* Links grouped next to Logo */}
						<div className="hidden items-center gap-8 md:flex">
							{links.map((link) => (
								<Link 
									key={link.label} 
									className={cn(
										"text-[15px] font-medium text-slate-600 hover:text-teal-600 dark:text-zinc-400 dark:hover:text-teal-400 transition-colors flex items-center gap-1.5", 
										pathname === link.href && "text-teal-600 dark:text-teal-400"
									)} 
									to={link.href}
								>
									{link.label}
								</Link>
							))}
						</div>
					</div>

					{/* Global Right Actions */}
					<div className="hidden ml-auto md:flex items-center gap-4">
						{user ? (
							<div className="relative" ref={profileRef}>
								<button
									onClick={() => setProfileOpen(!profileOpen)}
									className="flex items-center gap-2 pl-1 pr-3 py-1.5 rounded-full border border-border hover:border-teal-300 bg-white dark:bg-zinc-900 shadow-sm hover:shadow-md transition-all"
								>
									<img src={user.avatar} className="w-7 h-7 rounded-full bg-zinc-100 dark:bg-zinc-800" alt={user.name} />
									<span className="text-sm font-medium hidden sm:block max-w-[120px] truncate">{user.name}</span>
									<ChevronDown className={`w-3.5 h-3.5 text-muted-foreground transition-transform ${profileOpen ? "rotate-180" : ""}`} />
								</button>

								<AnimatePresence>
									{profileOpen && (
										<motion.div
											initial={{ opacity: 0, y: 8, scale: 0.96 }}
											animate={{ opacity: 1, y: 0, scale: 1 }}
											exit={{ opacity: 0, y: 8, scale: 0.96 }}
											className="absolute right-0 top-full mt-2 w-56 bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 shadow-xl py-2 z-50"
										>
											<div className="px-4 py-2.5 border-b border-zinc-100 dark:border-zinc-800 mb-1">
												<p className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">{user.name}</p>
												<p className="text-xs text-muted-foreground truncate">{user.email}</p>
											</div>
											{[
												{ icon: LayoutDashboard, label: "Dashboard", href: "/dashboard" },
												{ icon: BarChart2, label: "ATS Analysis", href: "/ats-analysis" },
											].map(({ icon: Icon, label, href }) => (
												<Link
													key={href}
													to={href}
													onClick={() => setProfileOpen(false)}
													className="flex items-center gap-3 px-4 py-2 text-sm text-foreground hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors"
												>
													<Icon className="w-4 h-4 text-muted-foreground" /> {label}
												</Link>
											))}
											<div className="border-t border-zinc-100 mt-1 pt-1">
												<button
													onClick={() => { signOut(); setProfileOpen(false) }}
													className="flex items-center gap-3 px-4 py-2 w-full text-sm text-rose-500 hover:bg-rose-50 transition-colors"
												>
													<LogOut className="w-4 h-4" /> Sign Out
												</button>
											</div>
										</motion.div>
									)}
								</AnimatePresence>
							</div>
						) : (
							<>
								<Button className="font-medium" variant="outline" onClick={openModal}>Sign In</Button>
								<Button variant="gradient" className="font-medium shadow-sm" onClick={openModal}>Get Started</Button>
							</>
						)}
					</div>

					<Button
						size="icon"
						variant="outline"
						onClick={() => setOpen(!open)}
						className="md:hidden ml-auto"
						aria-expanded={open}
						aria-controls="mobile-menu"
						aria-label="Toggle menu"
					>
						<MenuToggleIcon open={open} className="size-5" duration={300} />
					</Button>
				</nav>

				<MobileMenu open={open} className="flex flex-col justify-between gap-2 bg-background border-t pt-2">
					<div className="grid gap-y-2">
						{links.map((link) => (
							<Link
								key={link.label}
								className={cn(buttonVariants({
									variant: 'ghost',
									className: 'justify-start',
								}), pathname === link.href && "bg-accent")}
								to={link.href}
								onClick={() => setOpen(false)}
							>
								{link.label}
							</Link>
						))}

						{user && [
							{ icon: LayoutDashboard, label: "Dashboard", href: "/dashboard" },
							{ icon: BarChart2, label: "ATS Analysis", href: "/ats-analysis" },
						].map(({ icon: Icon, label, href }) => (
							<Link
								key={href}
								to={href}
								onClick={() => setOpen(false)}
								className={cn(buttonVariants({
									variant: 'ghost',
									className: 'justify-start',
								}))}
							>
								<Icon className="w-4 h-4 mr-2 text-muted-foreground" /> {label}
							</Link>
						))}
					</div>
					
					<div className="flex flex-col gap-2 mt-4 border-t pt-4">
						{user ? (
							<Button variant="destructive" onClick={() => { signOut(); setOpen(false); }} className="w-full">
								Sign Out
							</Button>
						) : (
							<>
								<Button variant="outline" className="w-full bg-transparent" onClick={() => { setOpen(false); openModal(); }}>
									Sign In
								</Button>
								<Button className="w-full" variant="gradient" onClick={() => { setOpen(false); openModal(); }}>
									Get Started
								</Button>
							</>
						)}
					</div>
				</MobileMenu>
			</header>
		</>
	);
}

type MobileMenuProps = React.ComponentProps<'div'> & {
	open: boolean;
};

function MobileMenu({ open, children, className, ...props }: MobileMenuProps) {
	if (!open || typeof window === 'undefined') return null;

	return createPortal(
		<div
			id="mobile-menu"
			className={cn(
				'bg-background/95 supports-[backdrop-filter]:bg-background/50 backdrop-blur-lg',
				'fixed top-14 lg:top-16 right-0 bottom-0 left-0 z-[45] flex flex-col overflow-y-auto px-4 md:hidden',
			)}
		>
			<div
				data-slot={open ? 'open' : 'closed'}
				className={cn(
					'ease-out transition-all animate-in slide-in-from-top-2 fade-in',
					'w-full pt-4 pb-12',
					className,
				)}
				{...props}
			>
				{children}
			</div>
		</div>,
		document.body,
	);
}
