import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', loadComponent: () => import('./storefront').then((module) => module.Storefront), title: 'Tienda Web' },
  { path: 'admin', loadComponent: () => import('./admin/admin').then((module) => module.Admin), title: 'Administración · Tienda Web' },
  { path: '**', redirectTo: '' },
];
